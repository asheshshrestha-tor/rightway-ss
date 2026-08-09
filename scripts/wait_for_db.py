"""Block until the database answers, then exit.

Run before `migrate` at container start.

Railway's private network (`*.railway.internal`) is IPv6-only and its DNS is
not ready the instant a container starts, so the first connection of a cold
boot fails with:

    OperationalError: (2005, "Unknown server host 'mysql.railway.internal' (-2)")

`-2` is EAI_NONAME - the name did not resolve. It is a timing problem far more
often than a configuration one, and retrying for a minute removes the whole
class of it. The same wait covers a database that is still booting, or one
restarting underneath a running app.

Exits 0 as soon as a connection succeeds, or 1 after DB_WAIT_SECONDS with an
explanation of what to check.
"""

from __future__ import annotations

import os
import socket
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connections  # noqa: E402

TIMEOUT = int(os.environ.get("DB_WAIT_SECONDS", "90"))
INTERVAL = 2


def resolves(host):
    """Whether the hostname resolves, over either IP version."""
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False


def main():
    database = settings.DATABASES["default"]
    host = database.get("HOST") or "localhost"

    if database["ENGINE"].endswith("sqlite3"):
        print("wait_for_db: SQLite needs no wait")
        return 0

    print(f"wait_for_db: waiting up to {TIMEOUT}s for {host}")

    deadline = time.monotonic() + TIMEOUT
    attempt = 0
    last_error = None

    while time.monotonic() < deadline:
        attempt += 1
        try:
            connections["default"].ensure_connection()
        except Exception as error:  # noqa: BLE001 - any failure means retry
            last_error = error
            # Close the failed connection, or Django hands the same broken one
            # back on the next attempt and it never recovers.
            connections["default"].close()
            if attempt == 1 or attempt % 5 == 0:
                print(f"wait_for_db: attempt {attempt} - {error}")
            time.sleep(INTERVAL)
        else:
            waited = TIMEOUT - int(deadline - time.monotonic())
            print(f"wait_for_db: connected after {waited}s")
            return 0

    print(f"\nwait_for_db: gave up after {TIMEOUT}s", file=sys.stderr)
    print(f"  last error: {last_error}", file=sys.stderr)
    print(f"  host       : {host}", file=sys.stderr)
    print(f"  resolves   : {resolves(host)}", file=sys.stderr)

    if not resolves(host) and host.endswith(".railway.internal"):
        print(
            "\n  The private hostname never resolved. Check that:\n"
            "    - the database and this app are in the SAME project AND the\n"
            "      same environment (production, staging - they do not share a\n"
            "      private network across environments);\n"
            "    - the service name in the hostname matches the database\n"
            "      service, which is what ${{MySQL.MYSQL_URL}} expands from -\n"
            "      rename the service and the hostname changes with it;\n"
            "    - the value really is a reference and not a stale copy of an\n"
            "      old URL pasted in by hand.\n"
            "\n  As a fallback, set DATABASE_URL to the database's\n"
            "  MYSQL_PUBLIC_URL. That works over the public internet, so it is\n"
            "  slower and billed as egress, but it proves whether the problem\n"
            "  is the private network or the credentials.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
