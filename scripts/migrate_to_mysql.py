"""Copy this project's data from its current database into MySQL.

    python scripts/migrate_to_mysql.py --to "mysql://user:pass@127.0.0.1:3306/rightway"

What it does, in order:

  1. Counts the rows in the source database, so the result can be checked.
  2. Checks it can reach MySQL, with a readable message if it cannot.
  3. Optionally creates the database with the right charset.
  4. Refuses to write into a database that already holds data.
  5. Dumps to a JSON fixture using natural keys.
  6. Runs `migrate` against MySQL to build the schema.
  7. Loads the fixture.
  8. Counts the rows again and compares. Any mismatch exits non-zero.

Nothing is deleted and the source is only ever read, so a failed run costs
nothing but time - fix the problem and run it again.

The fixture holds enquiries, consultations and job applications: real people's
names, addresses and phone numbers. It is written to `backups/`, which is
gitignored. Delete it once the migration is confirmed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
MANAGE = BASE_DIR / "manage.py"

# Rebuilt by `migrate`, so copying them across would collide on load.
EXCLUDED = [
    "contenttypes",
    "auth.permission",
    "sessions.session",
    "admin.logentry",
]

# Counted on both sides. Sessions are deliberately not migrated - everyone
# simply signs in again.
COUNTED = [
    ("auth", "User"),
    ("auth", "Group"),
    ("pages", "SiteSettings"),
    ("pages", "SocialLink"),
    ("pages", "Service"),
    ("pages", "TeamMember"),
    ("pages", "Vacancy"),
    ("pages", "Application"),
    ("pages", "Consultation"),
    ("pages", "Enquiry"),
]

# Run through a plain interpreter rather than `manage.py shell`, whose
# auto-import banner would land in the output being parsed.
COUNT_SNIPPET = (
    "import os, json, django;"
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings');"
    "django.setup();"
    "from django.apps import apps;"
    "print('__COUNTS__' + json.dumps({"
    + ",".join(
        f"'{app}.{model}': apps.get_model('{app}','{model}').objects.count()"
        for app, model in COUNTED
    )
    + "}))"
)


class Failure(Exception):
    """Something went wrong that the operator needs to read."""


def _environment(database_url):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    # Keep the run predictable regardless of what .env happens to say.
    environment["DEBUG"] = "False"
    # Windows defaults child output to the console codepage (cp1252 here), so
    # an em dash in a stored note would be written as byte 0x97 - which is not
    # valid UTF-8, and `loaddata` reads UTF-8. Force UTF-8 on both sides.
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def run(args, database_url, capture=False):
    """Run a manage.py command against a specific database."""
    result = subprocess.run(
        [sys.executable, str(MANAGE), *args],
        cwd=BASE_DIR,
        env=_environment(database_url),
        capture_output=capture,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        if capture:
            sys.stderr.write(result.stdout or "")
            sys.stderr.write(result.stderr or "")
        raise Failure(f"`manage.py {' '.join(args)}` failed.")
    return result


def row_counts(database_url, quiet=False):
    result = subprocess.run(
        [sys.executable, "-c", COUNT_SNIPPET],
        cwd=BASE_DIR,
        env=_environment(database_url),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    for line in result.stdout.splitlines():
        if line.startswith("__COUNTS__"):
            return json.loads(line[len("__COUNTS__") :])
    if not quiet:
        sys.stderr.write(result.stderr or "")
    raise Failure("Could not read row counts from that database.")


def check_connection(target_url):
    """Fail early, and readably, if MySQL is not reachable."""
    import MySQLdb

    parsed = urlparse(target_url)
    try:
        connection = MySQLdb.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=parsed.username or "",
            passwd=parsed.password or "",
            connect_timeout=10,
        )
    except MySQLdb.Error as error:
        code = error.args[0] if error.args else ""
        hint = {
            1045: "Wrong username or password.",
            2003: "No MySQL server answered. Is it running, and is the port right?",
            1044: "That user is not allowed to use this database.",
        }.get(code, "")
        raise Failure(
            f"Could not connect to MySQL: {error}\n"
            f"  {hint}\n"
            "  Special characters in the password must be percent-encoded "
            "(@ becomes %40, : becomes %3A, / becomes %2F)."
        )
    connection.close()
    host = parsed.hostname or "127.0.0.1"
    print(f"     connected to {host}:{parsed.port or 3306} as {parsed.username}")


def create_database(target_url):
    """CREATE DATABASE ... utf8mb4, if it is not already there."""
    import MySQLdb

    parsed = urlparse(target_url)
    name = parsed.path.lstrip("/")
    if not name:
        raise Failure("The target URL has no database name.")

    connection = MySQLdb.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        passwd=parsed.password or "",
    )
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        connection.commit()
    except MySQLdb.Error as error:
        raise Failure(f"Could not create `{name}`: {error}")
    finally:
        connection.close()
    print(f"     `{name}` is ready (utf8mb4 / utf8mb4_unicode_ci)")


def target_is_empty(target_url):
    """True when MySQL holds no data for us - a fresh, safe destination."""
    try:
        counts = row_counts(target_url, quiet=True)
    except Failure:
        # The tables do not exist yet, so there is nothing to overwrite.
        return True
    return sum(counts.values()) == 0


def main():
    parser = argparse.ArgumentParser(description="Copy this project's data into MySQL.")
    parser.add_argument(
        "--to",
        default=os.environ.get("MYSQL_URL", ""),
        help="Target, e.g. mysql://user:pass@127.0.0.1:3306/rightway",
    )
    parser.add_argument(
        "--from",
        dest="source",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        help="Source database URL. Defaults to the project's SQLite file.",
    )
    parser.add_argument(
        "--create-database",
        action="store_true",
        help="CREATE DATABASE on the target first (needs a user that may).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Load even if the target already holds data. It will be added to.",
    )
    parser.add_argument("--fixture", default="", help="Where to write the dump.")
    args = parser.parse_args()

    if not args.to:
        parser.error("--to is required (or set MYSQL_URL).")
    if not args.to.startswith("mysql://"):
        parser.error("--to must be a mysql:// URL.")

    fixture = Path(
        args.fixture
        or BASE_DIR / "backups" / f"data-{datetime.now():%Y%m%d-%H%M%S}.json"
    )
    fixture.parent.mkdir(parents=True, exist_ok=True)

    print("1. Reading the source database")
    before = row_counts(args.source)
    total = sum(before.values())
    for label, count in before.items():
        print(f"     {label:<24} {count}")
    print(f"     {'total':<24} {total}")
    if total == 0:
        raise Failure("The source database is empty - nothing to migrate.")

    print("\n2. Connecting to MySQL")
    check_connection(args.to)

    if args.create_database:
        print("\n3. Creating the database")
        create_database(args.to)
    else:
        print("\n3. Skipping creation (--create-database not given)")

    print("\n4. Checking the target is safe to write to")
    if target_is_empty(args.to):
        print("     target is empty")
    elif args.force:
        print("     target is not empty - continuing because --force was given")
    else:
        raise Failure(
            "The target already contains data. Drop and recreate it, point at "
            "a different database, or pass --force to add to it."
        )

    print(f"\n5. Dumping to {fixture.relative_to(BASE_DIR)}")
    dump = run(
        [
            "dumpdata",
            "--natural-foreign",
            "--natural-primary",
            *[arg for name in EXCLUDED for arg in ("--exclude", name)],
            "--indent",
            "2",
        ],
        args.source,
        capture=True,
    )
    fixture.write_text(dump.stdout, encoding="utf-8")
    print(f"     {len(dump.stdout):,} bytes")

    print("\n6. Building the schema in MySQL")
    run(["migrate", "--noinput"], args.to)

    print("\n7. Loading the data")
    run(["loaddata", str(fixture)], args.to)

    print("\n8. Verifying")
    mismatches = []
    after = row_counts(args.to)
    for label, expected in before.items():
        got = after.get(label, 0)
        if got != expected:
            mismatches.append(f"{label}: expected {expected}, got {got}")
        print(f"     {label:<24} {expected:>5} -> {got:<5} {'ok' if got == expected else 'MISMATCH'}")

    if mismatches:
        raise Failure("Row counts do not match:\n  " + "\n  ".join(mismatches))

    print("\nDone. Every row is accounted for.")
    print("\nNext:")
    print("  1. Put this in .env:")
    print(f"       DATABASE_URL={args.to}")
    print("  2. Restart the app and sign in to check.")
    print(f"  3. Delete {fixture.relative_to(BASE_DIR)} - it holds personal data.")
    print("\nUploaded files live on disk, not in the database, so media/ and")
    print("private-media/ carry over untouched.")


if __name__ == "__main__":
    try:
        main()
    except Failure as error:
        sys.stderr.write(f"\nStopped: {error}\n")
        sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover
        sys.stderr.write("\nInterrupted.\n")
        sys.exit(130)
