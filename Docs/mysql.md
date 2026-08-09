# Moving to MySQL

The project reads its database from `DATABASE_URL` in `.env`, so switching
engines is a configuration change, not a code change. This document covers the
one-off move of existing data from SQLite to MySQL.

Uploaded files live on disk, not in the database, so `media/` and
`private-media/` are unaffected. Nothing here deletes or modifies the SQLite
file — it stays as a fallback until you delete it yourself.

**Time:** about ten minutes. **Downtime:** the length of step 5.

---

## Before you start

You need:

- MySQL 8.0 or later, running and reachable.
- A MySQL account that can create a database and a user, for step 2.
- The dependencies installed: `pip install -r requirements.txt`.

Check the driver imported cleanly:

```bash
python -c "import MySQLdb; print(MySQLdb.__version__)"
```

If that fails on Linux or macOS, install the client headers first
(`sudo apt install default-libmysqlclient-dev build-essential`, or
`brew install mysql-client pkg-config`) and reinstall `mysqlclient`.

---

## 1. Create `.env`

```bash
cp .env.example .env
```

Generate a secret key and paste it in as `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Leave `DATABASE_URL` pointing at SQLite for now — you will switch it in step 6,
after the data has actually arrived:

```ini
DATABASE_URL=sqlite:///db.sqlite3
```

`.env` is gitignored. Never commit it.

---

## 2. Create the database and user

Sign in as an administrator (`mysql -u root -p`) and run:

```sql
CREATE DATABASE rightway
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'rightway'@'localhost' IDENTIFIED BY 'a-long-random-password';
GRANT ALL PRIVILEGES ON rightway.* TO 'rightway'@'localhost';
FLUSH PRIVILEGES;
```

`utf8mb4` matters. MySQL's older `utf8` is three bytes per character and cannot
store the full Unicode range — an emoji in an enquiry message would be rejected
or mangled. Use `'rightway'@'%'` instead of `'localhost'` if the database is on
a different host from the application.

The migration script can do this step for you with `--create-database`, but
only if the account in the URL is allowed to create databases. Creating a
dedicated, limited user by hand is the better habit.

---

## 3. Run the migration

One command. It reads SQLite and writes MySQL:

```bash
python scripts/migrate_to_mysql.py --to "mysql://rightway:a-long-random-password@127.0.0.1:3306/rightway"
```

If the password contains punctuation, percent-encode it — the URL parser will
otherwise split on it and the connection will fail with a confusing error:

| Character | `@` | `:` | `/` | `#` | `?` | `%` |
|---|---|---|---|---|---|---|
| Write as | `%40` | `%3A` | `%2F` | `%23` | `%3F` | `%25` |

The script works in eight steps and prints each one:

1. Counts every row in SQLite, so the result can be checked against it.
2. Connects to MySQL, with a readable message if it cannot.
3. Creates the database, if `--create-database` was passed.
4. **Refuses to continue if the target already holds data.** Pass `--force`
   only when you intend to add to what is there.
5. Dumps to a JSON fixture in `backups/`, using natural keys.
6. Runs `migrate` against MySQL to build the schema.
7. Loads the fixture.
8. Counts the rows again and compares. Any mismatch exits non-zero.

Expected output ends like this:

```
8. Verifying
     auth.User                    3 ->  3    ok
     ...
     pages.Enquiry               15 -> 15    ok

Done. Every row is accounted for.
```

Nothing is deleted and SQLite is only ever read, so a failed run costs nothing
but time. Fix the problem and run it again.

**Useful flags**

| Flag | What it does |
|---|---|
| `--create-database` | Runs `CREATE DATABASE` with the right charset first |
| `--from URL` | Migrate from something other than the project's SQLite file |
| `--force` | Load even though the target already holds data |
| `--fixture PATH` | Write the dump somewhere other than `backups/` |

---

## 4. Check the data

Point a shell at the new database and look at it before committing:

```bash
DATABASE_URL="mysql://rightway:...@127.0.0.1:3306/rightway" python manage.py shell
```

```python
from django.contrib.auth.models import User
from pages.models import Enquiry, SiteSettings

User.objects.count()                    # users came across
User.objects.get(username="admin").is_superuser
SiteSettings.load().name                # settings singleton is intact
Enquiry.objects.latest("created_at")     # most recent enquiry reads correctly
```

Password hashes migrate as-is, so everyone signs in with the password they
already had. Sessions are deliberately *not* migrated — anyone signed in will
simply be asked to sign in again.

---

## 5. Switch over

Edit `.env`:

```ini
DATABASE_URL=mysql://rightway:a-long-random-password@127.0.0.1:3306/rightway
```

Restart the application. In development that is just `runserver`; under
Gunicorn or uWSGI, restart the service.

Then sign in at `/dashboard/` and confirm the site loads, the logo appears, and
the enquiry list has its rows.

---

## 6. Load the timezone tables

Not optional — see [Timezone tables](#timezone-tables-required) below. Without
them the dashboard chart quietly reads zero on every day.

```sql
SELECT CONVERT_TZ('2026-08-09 01:00:00', 'UTC', 'Australia/Brisbane');
```

`NULL` means you need to do it.

---

## 7. Clean up

```bash
python manage.py test          # 264 tests, now against MySQL
rm backups/data-*.json         # contains personal data - see below
```

**Delete the fixture.** It holds enquiries, consultation requests and job
applications: real names, addresses and phone numbers in plain text. `backups/`
is gitignored so it will not be committed, but it should not sit on disk either.

Keep `db.sqlite3` for a few days as a fallback, then delete it too — it holds
the same personal data.

---

## If something goes wrong

**`Access denied for user ... (using password: YES)`**
Wrong username or password, or the password needs percent-encoding. Confirm the
credentials work directly: `mysql -u rightway -p rightway`.

**`No MySQL server answered`**
MySQL is not running, or the port is wrong. On Windows check the `MySQL80`
service; on Linux, `systemctl status mysql`.

**`The target already contains data`**
The safety check in step 4 fired. Either drop and recreate the database, or
pass `--force` if adding to it is genuinely what you want.

**`Row counts do not match`**
Something failed to load. The fixture in `backups/` is still there and SQLite
is untouched, so nothing is lost. Read the mismatch lines, drop the database,
recreate it and run again.

**Rolling back**
Put the SQLite URL back in `.env` and restart. The SQLite file was never
written to.

---

## Timezone tables (required)

**MySQL needs its timezone tables populated, or parts of the dashboard silently
show zero.**

The project runs with `USE_TZ = True` and `TIME_ZONE = "Australia/Brisbane"`.
For a query like `created_at__date__gte=...`, Django asks MySQL to convert the
stored UTC value with `CONVERT_TZ(created_at, 'UTC', 'Australia/Brisbane')`.
MySQL only knows named zones if `mysql.time_zone_name` has been loaded — and
when it does not, `CONVERT_TZ` returns `NULL` rather than raising. The rows
simply fail to match.

SQLite does this conversion in Python, so the problem only appears after moving
to MySQL. What breaks:

- the enquiries-over-time chart on the dashboard overview,
- the "N in the last 7 days" hint on the enquiries tile,
- `dashboard.tests.test_chart_series_is_zero_filled`, which is the cheapest way
  to detect it.

Check whether it applies to your server:

```sql
SELECT CONVERT_TZ('2026-08-09 01:00:00', 'UTC', 'Australia/Brisbane');
```

`2026-08-09 11:00:00` means it is fine. `NULL` means the tables are missing.

### Fix: load the full timezone database

The robust option, and what Django's documentation prescribes. On Linux/macOS:

```bash
mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root -p mysql
```

On Windows that tool ships no zoneinfo files, so download the prebuilt package
from <https://dev.mysql.com/downloads/timezones.html> (the POSIX archive for
MySQL 8) and import it:

```bash
mysql -u root -p mysql < timezone_posix.sql
```

### Fix: the single zone this project needs

Enough when the server is only ever used for this application. Brisbane has had
no daylight saving since 1992 and sits at a fixed UTC+10, so one
transition-free entry is accurate for any realistic data:

```sql
INSERT INTO mysql.time_zone (Use_leap_seconds) VALUES ('N');
SET @tz = LAST_INSERT_ID();

INSERT INTO mysql.time_zone_name (Name, Time_zone_id)
  VALUES ('Australia/Brisbane', @tz);

INSERT INTO mysql.time_zone_transition_type
  (Time_zone_id, Transition_type_id, Offset, Is_DST, Abbreviation)
  VALUES (@tz, 0, 36000, 0, 'AEST');
```

This is only correct while `TIME_ZONE` stays on Brisbane. Change it to a zone
with daylight saving, such as `Australia/Sydney`, and you need the full
database instead.

### Restart afterwards

**Either fix needs a MySQL restart to take effect.** The server caches timezone
lookups, including the failed ones, and `FLUSH TABLES` does not clear that
cache. On Windows, from an elevated prompt:

```powershell
net stop MySQL80 && net start MySQL80
```

On Linux: `sudo systemctl restart mysql`. Then re-run the `CONVERT_TZ` check
above and confirm it returns a time rather than `NULL`.

---

## Notes on the MySQL configuration

`config/settings.py` applies these automatically when the engine is MySQL:

- **`charset: utf8mb4`** — stores the full Unicode range.
- **`sql_mode: STRICT_TRANS_TABLES`** — without it, MySQL silently truncates a
  value that is too long for its column instead of raising, so bad data lands
  in the table unnoticed.
- **`CONN_MAX_AGE`** (default 60s) — reuses connections between requests rather
  than opening one each time. Set it to `0` behind an external connection
  pooler such as ProxySQL.
- **Test database charset** — so the test suite matches production.

The longest indexed column in this schema is 160 characters, comfortably under
InnoDB's 768-character limit for a `utf8mb4` index, so no column needs a prefix
index.
