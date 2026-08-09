# Deploying to Railway

Railway builds from a GitHub repository, runs the app in a container, and can
host the MySQL database alongside it.

This project ships a `Dockerfile`, so Railway builds from that rather than
guessing. That matters here: `mysqlclient` is a C extension needing the MySQL
headers and a compiler, which is the usual first thing to fail on a default
Python builder.

**Read [Two things that will bite you](#two-things-that-will-bite-you) before
you start.** Both cause silent data loss or silently wrong numbers rather than
an error.

---

## Two things that will bite you

### Uploaded files are deleted on every deploy

A container's filesystem does not survive a restart or a redeploy. Without a
volume, every logo, favicon, service image, team photo **and every applicant's
résumé** is gone the next time you push. Nothing warns you — the database rows
survive and the pages render with broken images.

The fix is a Railway **Volume**, mounted at `/data`, with `MEDIA_ROOT` and
`PRIVATE_MEDIA_ROOT` pointed into it. Step 5 covers it. Do not skip it.

### MySQL's timezone tables start empty

Railway's MySQL is a stock image, so `CONVERT_TZ` returns `NULL` and every
date-based figure on the dashboard reads zero without erroring. Same problem
documented in [mysql.md](mysql.md); step 7 applies it to Railway.

---

## 1. Push to GitHub

Railway deploys from a repository, so the code has to be there first.

```bash
git status                  # confirm .env and db.sqlite3 are NOT listed
git add .
git commit -m "Add deployment configuration"
git push origin main
```

`.gitignore` already excludes `.env`, `db.sqlite3`, `media/`, `private-media/`,
`backups/` and SSH keys. Check `git status` anyway before the first push — a
secret is far easier to keep out than to remove from history.

## 2. Create the project

1. <https://railway.com> → **New Project** → **Deploy from GitHub repo**.
2. Authorise Railway for the repository and pick it.

The first build will fail, or the app will boot and error. That is expected —
there is no database and no configuration yet.

## 3. Add MySQL

In the project canvas: **New** → **Database** → **Add MySQL**.

Railway creates the service and exposes connection variables on it. Open its
**Variables** tab and note:

- `MYSQL_URL` — the internal address, used by the app.
- `MYSQL_PUBLIC_URL` — reachable from your machine, used to load the data.

## 4. Configure the app service

Open the app service → **Variables** → **Raw Editor**, and paste:

```ini
DATABASE_URL=${{MySQL.MYSQL_URL}}
SECRET_KEY=paste-a-generated-key-here
DEBUG=False
ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}}
CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}

MEDIA_ROOT=/data/media
PRIVATE_MEDIA_ROOT=/data/private-media

TRUST_PROXY_SSL_HEADER=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000

DEFAULT_FROM_EMAIL=no-reply@rightwaysupportservices.com.au
CONTACT_EMAIL=arshdeep@rightwaysupportservices.com.au

# How long to wait at boot for the private network to come up.
DB_WAIT_SECONDS=90
```

The `${{MySQL.MYSQL_URL}}` syntax is a Railway reference — it resolves at
deploy time, so the password is never copied around. Adjust `MySQL` if you
renamed the database service.

Generate the secret key locally and paste the result:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**`TRUST_PROXY_SSL_HEADER` is not optional here.** Railway terminates TLS at its
edge and forwards plain HTTP, so Django sees an insecure request; with
`SECURE_SSL_REDIRECT=True` and no proxy header it redirects to itself forever
and the site is unreachable.

Email stays on the console backend unless you configure SMTP — see step 9.

## 5. Add the volume

App service → **Settings** → **Volumes** → **Add Volume**, mount path `/data`.

This is what makes uploads survive a deploy, and it is why `MEDIA_ROOT` and
`PRIVATE_MEDIA_ROOT` point into `/data` above.

A volume attaches to one service and cannot be shared, so keep the app at
**one replica**. Two replicas would also race each other running `migrate` at
boot.

### Why this is needed

The image is rebuilt from the repository on every deploy, and the container
filesystem starts empty. Anything written at runtime — an uploaded logo, a
service photo, an applicant's résumé — exists only in that container. Push a
commit, or let Railway restart the service, and it is gone. The database rows
survive, so the site keeps rendering with broken images and applications whose
résumé link 404s. Nothing errors, which is what makes it dangerous.

A volume is real disk that outlives the container. Mounted at `/data`, with
both roots pointed into it, uploads survive deploys and restarts.

Two directories, deliberately separate:

| Setting | Path | Served how |
|---|---|---|
| `MEDIA_ROOT` | `/data/media` | Publicly, at `/media/...` |
| `PRIVATE_MEDIA_ROOT` | `/data/private-media` | Only via a permission-checked view |

Résumés live in the second one. It has no URL of its own — the only way to read
a file there is `/dashboard/applications/<pk>/resume/`, behind the
`pages.view_application` permission. **Never point `MEDIA_ROOT` at `/data`
itself**, or the private tree ends up inside the public one and every résumé
becomes downloadable by guessing a URL. `dashboard.tests_careers.MediaLayoutTests`
asserts they stay separate.

### Restoring images you had locally

Uploaded files are not in the repository — `media/` is gitignored, and the data
migration copies database rows, not files. After deploying, re-upload through
the dashboard anything you had uploaded locally: logo, favicon, service images,
team photos.

Services and team members without an uploaded image fall back to the artwork
shipped in `static/`, so those pages render either way.

### When a volume is not enough

A volume is right for one instance, which is what this project needs. Move to
object storage (S3, Cloudflare R2, Backblaze B2) if you ever need more than one
replica, since a volume cannot be shared between them, or want backups and CDN
delivery of uploads.

That means `django-storages` and a `STORAGES["default"]` backend. The résumé
download already goes through Django's storage API rather than a filesystem
path, so it ports without changes — but keep the bucket **private** and keep
serving résumés through the permission-checked view, never a public URL.

## 6. Generate a domain

App service → **Settings** → **Networking** → **Generate Domain**.

`RAILWAY_PUBLIC_DOMAIN` now has a value, so the `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` references resolve. Redeploy if the service started
before the domain existed.

For a custom domain, add it in the same place and extend both variables:

```ini
ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}},rightwaysupportservices.com.au,www.rightwaysupportservices.com.au
CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}},https://rightwaysupportservices.com.au,https://www.rightwaysupportservices.com.au
```

## 7. Load the timezone tables

Connect with `MYSQL_PUBLIC_URL` from the MySQL service's Variables tab:

```bash
mysql -h HOST -P PORT -u root -p railway
```

Check first — `NULL` means it needs doing:

```sql
SELECT CONVERT_TZ('2026-08-09 01:00:00', 'UTC', 'Australia/Brisbane');
```

Then insert the one zone this project uses:

```sql
INSERT INTO mysql.time_zone (Use_leap_seconds) VALUES ('N');
SET @tz = LAST_INSERT_ID();

INSERT INTO mysql.time_zone_name (Name, Time_zone_id)
  VALUES ('Australia/Brisbane', @tz);

INSERT INTO mysql.time_zone_transition_type
  (Time_zone_id, Transition_type_id, Offset, Is_DST, Abbreviation)
  VALUES (@tz, 0, 36000, 0, 'AEST');
```

**Restart the MySQL service from the Railway dashboard afterwards.** MySQL
caches timezone lookups including the failed ones, and `FLUSH TABLES` does not
clear that cache. Re-run the `SELECT` and confirm it returns `11:00:00`.

If the managed database does not allow writing to the `mysql` schema, use a
`DATABASE_URL` with `?init_command=SET time_zone='+10:00'`, or move
`TIME_ZONE` to `"UTC"` and format for Brisbane in the templates instead.

## 8. Copy the data up

The app's `migrate` runs on boot, so the tables already exist — but they are
empty. Load your local data with the same script used for the local migration,
pointed at the **public** URL:

```bash
python scripts/migrate_to_mysql.py \
  --from "mysql://root:root@127.0.0.1:3306/rightway-db" \
  --to "mysql://root:PASSWORD@HOST:PORT/railway" \
  --force
```

`--force` is needed because `migrate` has already created Django's own rows
there. It verifies row counts on both sides and exits non-zero on a mismatch.

Then **delete the fixture it wrote to `backups/`** — it contains enquiries,
applications and consultation requests in plain text.

Skip this step entirely if you would rather start with an empty site; create an
administrator instead, from the service's shell:

```bash
python manage.py createsuperuser
```

## 9. Set up real email

The console backend prints to the log and sends nothing, so contact forms,
consultation confirmations and password resets all silently go nowhere. Add:

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-username
EMAIL_HOST_PASSWORD=your-password
```

Use a transactional provider such as Postmark, SendGrid, Mailgun or SES.
Consumer Gmail will rate-limit and eventually block this.

Test it by submitting the contact form and confirming the mail arrives.

Every enquiry, job application and consultation request sends two emails: a
notification to the staff who can act on it, with a button through to the
record, and a confirmation to the person who submitted it. Until SMTP is
configured both are printed to the service log and delivered nowhere.

Check the routing before trusting it:

```bash
python manage.py test_notifications
```

To test on a live site without emailing the client or a real applicant, set
`EMAIL_REDIRECT_TO=you@example.com`. Every message then goes to you instead,
with the intended recipients written into the subject line. Remove it when
you are done - with it set, nobody receives anything.

## 10. Check it

Open the generated domain and confirm:

- [ ] The site loads over HTTPS with no redirect loop.
- [ ] The logo, CSS and icons render — if not, `collectstatic` or WhiteNoise is
      the place to look.
- [ ] `/dashboard/` accepts your login.
- [ ] The overview chart shows real bars, not a flat zero line (step 7).
- [ ] Uploading a logo under Settings works, and **survives a redeploy** (step 5).
- [ ] A test enquiry saves and its email arrives (step 9).
- [ ] `/dashboard/applications/<pk>/resume/` downloads for a permitted user and
      404s when signed out.

## 11. Secure it

- **Change every password.** `admin` / `rightway-dev-2026` and the two
  dashboard users ship with development passwords, and they came across with
  the data:
  ```bash
  python manage.py changepassword admin
  ```
- Remove sample data if this is a fresh start: `python manage.py seed_dashboard --clear`.
- Rotate the local MySQL `root:root` credentials if that server is reachable
  from anywhere but your own machine.
- Set a retention policy for applicant résumés. They are personal information,
  and keeping them indefinitely is a liability rather than an asset.

---

## When something goes wrong

**Build fails compiling `mysqlclient`**
Railway is not using the `Dockerfile`. Check the app service's **Settings →
Build** and make sure the builder is Dockerfile, and that the file is committed
at the repository root.

**`DisallowedHost` in the logs**
`ALLOWED_HOSTS` does not include the domain being used. Generate the domain
(step 6) and redeploy so the reference resolves.

**Too many redirects**
`SECURE_SSL_REDIRECT=True` without `TRUST_PROXY_SSL_HEADER=True`. See step 4.

**CSRF verification failed on any form**
`CSRF_TRUSTED_ORIGINS` needs the scheme: `https://host`, not `host`.

**CSS and images 404, site renders unstyled**
`collectstatic` did not run, or WhiteNoise is not in `MIDDLEWARE` directly
after `SecurityMiddleware`. Check the build log.

**Images vanished after a deploy**
The volume is missing or `MEDIA_ROOT` is not pointed into it. The files are
gone; re-upload them, then fix step 5 before it happens again.

**Uploaded images 404, but files shipped in `static/` are fine**
Different mechanisms: `static/` is baked into the image and served by
WhiteNoise, while uploads are served by Django from `MEDIA_ROOT`. Check
`SERVE_MEDIA` is not set to `False`, and that `MEDIA_ROOT` points at the volume
and the file is actually on it.

**Dashboard charts are flat zero**
The timezone tables. Step 7.

**`Unknown server host 'mysql.railway.internal' (-2)`**

`-2` is EAI_NONAME: the name did not resolve. The private network is IPv6-only
and is not up at the instant a container starts, so anything touching the
database in the first moments of a cold boot fails this way. It reads like a
configuration error and usually is not one.

The container start command runs `scripts/wait_for_db.py` first, which retries
for `DB_WAIT_SECONDS` (default 90) before giving up, so a slow private network
resolves itself. Raise it if the logs show it timing out:

```ini
DB_WAIT_SECONDS=180
```

If it never resolves, the wait script prints what to check. In short:

- The database and the app must be in the **same project and the same
  environment**. Private networking does not cross environments, so an app in
  `production` cannot see a database in `staging`.
- The hostname comes from the **service name** — `${{MySQL.MYSQL_URL}}` expands
  to `mysql.railway.internal` because the service is called `MySQL`. Renaming
  the service changes the hostname.
- Confirm `DATABASE_URL` is a live `${{...}}` reference and not a URL pasted in
  by hand, which goes stale when credentials rotate.

To determine quickly whether it is the network or the credentials, point
`DATABASE_URL` at the database's `MYSQL_PUBLIC_URL` and redeploy. If that
works, the credentials are fine and the problem is private networking. It is a
reasonable way to get running today, but move back to the private URL when you
can — public traffic is slower and billed as egress.
