# Rightway Support Services

Django implementation of the eight-page design in `Docs/design.png`, using the
brand mark in `Docs/logo.png`.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
python manage.py migrate
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

Run the tests with `python manage.py test`.

## Configuration

Everything that differs between machines — the secret key, the database, mail,
debug — is read from a `.env` file in the project root. `.env.example` is the
annotated template; copy it and fill it in. `.env` is gitignored and must never
be committed.

Real environment variables take precedence over the file, so a hosting panel or
a systemd unit can supply values without editing anything on disk.

The defaults are chosen so a fresh clone runs with no `.env` at all: SQLite, and
email printed to the terminal.

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | insecure placeholder | Generate a real one for anything public |
| `DEBUG` | `False` | Never `True` on a public server |
| `ALLOWED_HOSTS` | empty | Comma separated. Required once `DEBUG=False` |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | See below |
| `CONN_MAX_AGE` | `60` | Seconds to hold a MySQL connection open |
| `EMAIL_BACKEND` | console | Switch to SMTP to send for real |
| `MEDIA_ROOT` | `./media` | Public uploads |
| `PRIVATE_MEDIA_ROOT` | `./private-media` | Resumes. Never web-served |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` | off | Turn on once TLS is in front |

### Database

`DATABASE_URL` selects the engine:

```ini
DATABASE_URL=sqlite:///db.sqlite3
DATABASE_URL=mysql://rightway:secret@127.0.0.1:3306/rightway
```

Punctuation in a MySQL password must be percent-encoded (`@` → `%40`,
`:` → `%3A`, `/` → `%2F`).

To move existing data from SQLite to MySQL, run:

```bash
python scripts/migrate_to_mysql.py --to "mysql://rightway:secret@127.0.0.1:3306/rightway"
```

It dumps, migrates, loads and then verifies the row counts on both sides,
exiting non-zero on any mismatch. SQLite is only ever read. Full walkthrough,
including the `CREATE DATABASE` statement and troubleshooting, is in
[Docs/mysql.md](Docs/mysql.md).

## Pages

| Route             | Name             | Template                          |
| ----------------- | ---------------- | --------------------------------- |
| `/`               | `home`           | `pages/home.html`                 |
| `/about/`         | `about`          | `pages/about.html`                |
| `/about/team/<slug>/` | `team_member` | `pages/team_member.html`        |
| `/services/`      | `services`       | `pages/services.html`             |
| `/services/<slug>/` | `service_detail` | `pages/service_detail.html`     |
| `/ndis-support/`  | `ndis_support`   | `pages/ndis_support.html`         |
| `/careers/`       | `careers`        | `pages/careers.html`              |
| `/careers/apply/` | `apply`          | `pages/apply_speculative.html`    |
| `/careers/<slug>/`| `vacancy_detail` | `pages/vacancy_detail.html`       |
| `/contact/`       | `contact`        | `pages/contact.html`              |
| `/book-a-consultation/` | `consultation` | `pages/consultation.html`   |
| `/faq/`           | `faq`            | `pages/faq.html`                  |
| `/privacy-policy/`| `privacy_policy` | `pages/privacy_policy.html`       |
| `/terms/`         | `terms`          | `pages/terms.html`                |

### Staff dashboard

| Route                     | Name                       | Purpose                          |
| ------------------------- | -------------------------- | -------------------------------- |
| `/dashboard/`               | `dashboard:index`            | Stats, enquiry chart, recent activity |
| `/dashboard/login/`         | `dashboard:login`            | Staff sign in                  |
| `/dashboard/logout/`        | `dashboard:logout`           | Sign out (POST only)           |
| `/dashboard/password-reset/`| `dashboard:password_reset`   | Forgot password                |
| `/dashboard/account/`       | `dashboard:account`          | Your own profile               |
| `/dashboard/account/password/` | `dashboard:password_change` | Change your own password    |
| `/dashboard/services/`      | `dashboard:service_list`     | Add / edit / order services    |
| `/dashboard/team/`          | `dashboard:team_list`        | Meet Our Team members          |
| `/dashboard/settings/`      | `dashboard:site_settings`    | Logo, favicon, contact, footer, map, socials |
| `/dashboard/vacancies/`     | `dashboard:vacancy_list`     | Advertise and close roles      |
| `/dashboard/applications/`  | `dashboard:application_list` | Job applications + resumes     |
| `/dashboard/consultations/` | `dashboard:consultation_list`| Confirm consultation times     |
| `/dashboard/enquiries/`     | `dashboard:enquiry_list`     | Contact form submissions       |
| `/dashboard/users/`         | `dashboard:user_list`        | User list / add / edit / delete|
| `/dashboard/roles/`         | `dashboard:group_list`       | Roles (auth groups) + permissions|

The design mockup does not include a Terms page, but its footer links to one, so
`/terms/` was added to make that link resolve.

## Structure

- `config/` - settings, URLs, WSGI/ASGI entry points
- `pages/`
  - `models.py` - `Service` and `Enquiry`
  - `vacancy_models.py` - `Vacancy`, `Application`, and the private storage
    used for resumes
  - `site_models.py` - `SiteSettings` (singleton) and `SocialLink`
  - `team_models.py` - `TeamMember`
  - `consultation_models.py` - `Consultation` and the business-day helper
  - `consultation_mail.py` - the three consultation emails
  - `content.py` - remaining static copy (values, team, FAQs, policy text) in
    one place, so wording can change without touching templates
  - `context_processors.py` - injects contact details, service list and social
    links into every template for the header and footer
  - `forms.py` - contact enquiry form, including the honeypot spam trap
  - `views.py` - one view per page, plus enquiry email delivery
- `templates/`
  - `base.html` - page shell (head, header, main, CTA band, footer)
  - `partials/` - header, footer, CTA band, breadcrumbs, feature strip, icon sprite
  - `pages/` - one template per page
- `dashboard/`
  - `access.py` - `staff_required` / `permission_required` decorators
  - `navigation.py` - permission-filtered sidebar menu + context processor
  - `forms.py` - user, role and enquiry forms with Metronic widget classes
  - `views.py` - dashboard home, user CRUD, role CRUD, enquiry handling
  - `management/commands/seed_dashboard.py` - sample data for local dev
- `static/css/style.css` - the public site design system
- `static/js/main.js` - mobile nav, dropdown menus, FAQ accordion
- `static/images/` - logo variants and placeholder artwork
- `static/metronic/` - Metronic 8.2.5 "demo29" theme assets (see below)
- `static/dashboard/` - project CSS/JS layered on top of Metronic

## Design system

Tokens live in the `:root` block of `static/css/style.css`.

| Token                          | Value     | Used for                          |
| ------------------------------ | --------- | --------------------------------- |
| `--green` / `--green-dark`     | `#166534` / `#14532d` | Primary buttons, icons |
| `--green-mid`                  | `#1e7a3c` | Secondary headings, eyebrows      |
| `--leaf`                       | `#7cb342` | Logo green, footer link hover     |
| `--navy`                       | `#0b2545` | Footer                            |
| `--ink`                        | `#12284c` | Headings                          |
| `--blue`                       | `#1d4ed8` | Links, CTA gradient end           |

Headings use Poppins and body copy uses Inter, loaded from Google Fonts with a
system-font fallback.

Repeated blocks are partials rather than copy-paste: the green-to-blue CTA band
above the footer is `partials/cta_band.html`, and each page overrides its copy:

```django
{% block cta %}
    {% include "partials/cta_band.html" with cta_title="Join Our Team" cta_label="View Current Vacancies" cta_icon="community" %}
{% endblock %}
```

Icons are a single inline SVG sprite (`partials/icon_sprite.html`) referenced as
`<svg aria-hidden="true"><use href="#i-heart"></use></svg>`.

## Images

`Docs/logo.png` ships with an opaque checkerboard baked into the background. The
version in `static/images/logo.png` has that removed, and `logo-light.png` is a
white treatment for the navy footer.

Every photograph in the design is currently a brand-toned SVG placeholder in
`static/images/` (`hero-*.svg`, `service-*.svg`, `team-*.svg`, `faq-support.svg`).
To use real photography, drop the file in and update the extension in the
matching template - or in `pages/content.py` for the service and team images.
See `static/images/README.md` for the full list and recommended sizes.

## Contact form

The enquiry form posts to the same URL, re-renders with inline errors when
invalid, and redirects with a success message when valid. Submissions are
emailed to `CONTACT_EMAIL`.

`EMAIL_BACKEND` defaults to the console backend, so enquiries print to the
terminal and nothing needs configuring to try it out. For production, set SMTP
credentials in `config/settings.py`:

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "..."
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "..."
EMAIL_HOST_PASSWORD = "..."
```

## Staff dashboard

`/dashboard/` is a Metronic-skinned back office that replaces Django's admin as
the primary interface. Django's own admin is still mounted at `/admin/` as a
fallback - delete that line from `config/urls.py` to remove it.

### Access model

Two layers, both enforced server side:

1. **Staff gate.** Every view requires `is_active` and `is_staff`. Anonymous
   users are redirected to `/dashboard/login/`; signed-in non-staff get a 403.
   The login form itself also rejects non-staff accounts.
2. **Model permissions.** Each section additionally requires the relevant
   Django permission, e.g. `auth.view_user` for the user list, `auth.add_user`
   to create one, `pages.change_enquiry` to update an enquiry. Superusers pass
   automatically.

Sections a user lacks permission for are removed from the sidebar as well as
being blocked, so the menu only ever shows what that person can actually open.

**The overview obeys the same rule.** Each tile and panel is built only when
the viewer holds the matching permission - and the view does not run the query
at all otherwise. A count is information in its own right: telling someone
"12 users" when they cannot open the user list still leaks how many users
exist.

| Overview block | Permission |
| -------------- | ---------- |
| Consultations to confirm, Upcoming Consultations | `pages.view_consultation` |
| Enquiries tile, chart, By-status, Recent Enquiries | `pages.view_enquiry` |
| New applications, Recent Applications | `pages.view_application` |
| Open vacancies, Vacancies content row | `pages.view_vacancy` |
| Services content row | `pages.view_service` |
| Team members content row | `pages.view_teammember` |
| Users tile, Newest Users | `auth.view_user` |
| Roles tile, role membership list | `auth.view_group` |

A staff member with no module permissions gets a plain welcome panel telling
them to ask an administrator for a role, rather than an empty grid.

### Users and roles

- **Users** - create, edit and delete accounts, set first/last name and email,
  toggle *Active*, *Dashboard access* (`is_staff`) and *Full administrator*
  (`is_superuser`), and assign roles. Password is required on create and
  optional on edit (blank keeps the existing one). You cannot delete the
  account you are signed in as.
- **Roles** are Django `auth.Group` records. A role is a name plus a set of
  permissions, shown grouped by the model they apply to. A user receives the
  combined permissions of every role they hold; full administrators bypass
  roles entirely.

### Signing in and out

Sign out from the avatar menu (top right); the account page carries a second
button for convenience. Both POST to `/dashboard/logout/` - `GET` returns 405,
so a stray link or a browser prefetch cannot end someone's session.

**Forgot password** is linked from the sign-in page. Only `is_staff` and
`is_active` accounts can reset this way, so a public-site contact whose email
happens to match a user record cannot trigger a reset. The confirmation screen
is identical whether or not the address matched, so the form cannot be used to
discover which addresses have accounts.

Reset mail goes through `EMAIL_BACKEND`, which is the console backend by
default - during development the link is printed to the terminal running
`runserver`.

**Change password** is at `/dashboard/account/password/`, reachable from the
avatar menu and the account page. It requires the current password and keeps
the session alive afterwards.

**My Account** lets any staff member edit their own name and email without
needing `auth.change_user`. It deliberately excludes `is_staff`,
`is_superuser` and roles - changing your own access level belongs on the Users
screen, behind permissions.

### Appearance (dark mode)

The avatar menu has an **Appearance** submenu with Light / Dark / System. The
behaviour is Metronic's own `KTThemeMode`, which persists the choice to
`localStorage` and sets `data-bs-theme` on `<html>`. Every template resolves
the stored value in a small inline script before first paint, so there is no
flash of the wrong theme on load.

Charts re-read their colours from CSS custom properties on
`kt.thememode.change`, so they re-render correctly when the theme flips.

### Services

Services are database records, editable at `/dashboard/services/`. Each one
drives, from a single source:

- the four cards on the home page (lowest `order` first)
- the services listing at `/services/`
- its own page at `/services/<slug>/`
- the header's Services dropdown
- the footer's "Our Services" column (when *Show in footer* is ticked)

Fields worth knowing:

| Field | Where it shows |
| ----- | -------------- |
| `summary` | Home page card, one line |
| `description` | Services listing card, and the detail page intro |
| `body` | The detail page's main text. Falls back to `description` |
| `highlights` | "What's Included" tick list - one item per line |
| `icon` | Picked from the site's SVG sprite, with a live preview |
| `image` | Uploaded to `MEDIA_ROOT/services/`; a placeholder is used when empty |
| `order` | Lower numbers first |
| `is_published` | Unticking hides it everywhere without deleting it |

The slug is generated from the title if left blank, and collisions get a
numeric suffix. Changing an existing slug changes that service's URL, so old
links will 404 - the field sits under "Search engines" with that in mind.

Images upload to `MEDIA_ROOT` (`media/`, gitignored). `config/urls.py` serves
them only when `DEBUG` is on; in production the web server should serve
`MEDIA_ROOT` at `MEDIA_URL`.

The five original services were moved from the old hardcoded list into the
database by `pages/migrations/0004_seed_services.py`, which also holds their
original copy.

### Site settings

Everything that is neither a page nor a list - the details most likely to
change and least likely to warrant a developer - lives in one editable row at
`/dashboard/settings/`, behind `pages.change_sitesettings`.

| Setting | Where it shows |
| ------- | -------------- |
| Name, tagline | Page titles, header alt text, footer |
| Logo | Site header |
| Logo (light) | The navy footer. Falls back to the main logo |
| Favicon | Browser tab on **both** the website and the dashboard |
| Footer description | The paragraph under the footer logo |
| Phone | Contact page, service pages, consultation page, footer, and quoted in consultation emails |
| Email | Contact page and footer - **and where enquiries, applications and consultation requests are sent** |
| Address, office hours | Contact page and footer |
| ABN | Footer bar, only when set |
| Map address / embed URL | The map at the bottom of the contact page |
| Social links | The footer's "Follow Us" row |

Things worth knowing:

- **The `tel:` link is derived, never stored.** Typing `0470 522 587` produces
  `tel:+61470522587` automatically, so the display number and the link cannot
  drift apart.
- **Uploads are optional.** With no logo or favicon uploaded, the site falls
  back to the files shipped in `static/images/`, so nothing ever renders broken.
- **Social links are a formset on the same page**, not a separate CRUD - six
  rows plus a blank one for adding another. *Show* is the only thing that
  decides visibility: a ticked row renders its icon **even with no URL yet**,
  pointing at `#` so there is never an empty or broken link. Those placeholder
  icons are dimmed and marked `aria-disabled`, and real links get
  `target="_blank" rel="noopener"`. Untick a row to hide it; if none are
  showing, the whole "Follow Us" column disappears rather than leaving an
  empty heading.
- The email address here overrides `CONTACT_EMAIL` in `config/settings.py`,
  which remains as the fallback if the field is ever cleared.

The original hardcoded values were moved into the database by
`pages/migrations/0011_seed_site_settings.py`.

### Team

The **Meet Our Team** section on the About page is database-backed, editable at
`/dashboard/team/`. Each published member also gets a profile page at
`/about/team/<slug>/` - for a disability support provider, who will actually be
supporting you is part of the decision, so bios and qualifications are worth
surfacing.

| Field | Where it shows |
| ----- | -------------- |
| `name`, `role` | The About page card and the profile heading |
| `photo` | Card and profile, with a live preview before saving |
| `bio` | The profile page body |
| `qualifications` | A tick list in the profile hero - one per line |
| `order` | Lower numbers first |
| `is_published` | Unticking hides the card *and* 404s the profile |

Photos follow the same three-step fallback as services: uploaded image, then a
slug-specific placeholder, then a generic one - so someone added by an
administrator never renders a broken image.

The four original members were moved from the hardcoded list into the database
by `pages/migrations/0009_seed_team.py`, which also carries their original roles
plus new bios and qualifications.

### Consultations

"Book a Free Consultation" is the site's primary call to action - it appears on
the home page, About, Services, every service page, NDIS Support and Contact,
and it is the default label of the CTA band. All of it now leads to
`/book-a-consultation/`.

**It is a request, not a live calendar.** The site tells visitors "we will
respond within one business day and arrange a time that suits you", so the
visitor states their availability and staff confirm the exact time. Building
self-service slot booking would contradict that promise and require staff
availability management.

What the form collects, and why:

| Field | Why it is asked |
| ----- | --------------- |
| Who the consultation is for | Distinguishes a participant from a family member or support coordinator |
| NDIS plan status | Decides what the consultation can usefully cover |
| Services of interest | Links to `Service`; preselected when arriving from a service page |
| Home visit / phone / video | The FAQ offers home visits, which need a location |
| Suburb + postcode | Only required for a home visit - the service area is Toowoomba and surrounds |
| Preferred date and time window, plus an alternative | Gives staff two options to work with on the confirming call |

Validation encodes the same promises: weekends are rejected because the office
is open Mon-Fri, and the earliest selectable date is the **next business day**
because same-day would be a promise the office cannot keep.

Each request gets a short reference (`RW-26-0001`) quoted in every email and on
the confirmation screen.

**Three emails.** The participant gets an immediate acknowledgement with their
reference; the office gets a notification; and when staff set a time in the
dashboard, the participant gets a confirmation with the agreed date. The
confirmation is sent **once** - re-saving a confirmed booking does not resend -
and can be suppressed with a checkbox if staff would rather phone.

The dashboard flags requests still unanswered after one business day as
**Overdue**, and the dashboard home shows how many are waiting plus the next
few confirmed appointments.

### Vacancies and applications

Vacancies are database records, editable at `/dashboard/vacancies/`. Each one
drives the list on `/careers/` and its own advert at `/careers/<slug>/`.

A vacancy is **open** when it is published and either has no closing date or
the closing date has not passed. Past the closing date the advert stays
readable - so a link in an email still works - but the application form is
replaced with a note and a link to current roles. `POST`ing to a closed
vacancy is rejected server side too, not just hidden in the template.

Applications arrive from two places: a specific advert, or the speculative
"send us your resume" page at `/careers/apply/`. Both land in
`/dashboard/applications/`, filterable by role, status, and assigned staff
member. The advertised title is copied onto the application at submission
time, so deleting a vacancy leaves its applications readable rather than
orphaned.

#### Resumes are private

Resumes are personal information, so they are handled differently from other
uploads:

- They are stored in `PRIVATE_MEDIA_ROOT` (`private-media/`, gitignored),
  **outside** `MEDIA_ROOT`. Nothing serves that directory, so a resume cannot
  be fetched by guessing a URL.
- The only way to read one is `/dashboard/applications/<pk>/resume/`, which
  requires `pages.view_application`. Anonymous users are redirected to the
  login page; signed-in non-staff and staff without the permission get a 403.
- Resumes are never emailed. The notification to the office contains the
  applicant's details and a pointer to open the file in the dashboard.
- Uploads are validated server side for extension and size
  (`RESUME_ALLOWED_EXTENSIONS`, `RESUME_MAX_BYTES`), because the `accept`
  attribute on a file input is only a hint a client can ignore.

**In production, do not add `private-media/` to your web server's static or
media configuration.** Serving it directly would bypass every check above.

### Enquiry filters

The enquiry list filters by free text, status, and **assigned user** -
*Anyone*, *Assigned to me*, *Unassigned* (with a live count), or a specific
staff member. Filters combine, and are preserved across pagination.

### Sample data

```bash
python manage.py seed_dashboard          # 2 roles, 2 staff users, 10 enquiries
python manage.py seed_dashboard --clear  # remove them again
```

Idempotent, so it is safe to re-run. The staff accounts it creates
(`phandler`, `mmanager`) use the password `dashboard-dev-2026` and are for
local development only.

### Theme assets

`static/metronic/` holds the parts of Metronic 8.2.5 "demo29" the dashboard
uses - roughly 9 MB of the theme's 73 MB:

| Path                                  | What                                   |
| ------------------------------------- | -------------------------------------- |
| `css/style.bundle.css`                | Theme stylesheet                       |
| `plugins/global/plugins.bundle.{css,js}` | Bootstrap 5.3, ApexCharts, jQuery   |
| `plugins/global/fonts/`               | keenicons + bootstrap-icons            |
| `js/scripts.bundle.js`                | Layout engine (reads the `data-kt-*` attributes) |
| `js/widgets.bundle.js`                | Theme widget modules                   |

The demo media library, DataTables, vis-timeline and the unused icon fonts
were left out.

Three things to know when working with this theme:

- Dropdowns need **`data-kt-menu="true"` on the menu element**, not just
  `data-kt-menu-trigger` on the thing you click. Without it `KTMenu` never
  binds and the menu silently does nothing.
- Flex children in Metronic's fixed-width menus need `min-width: 0` before
  `text-truncate` will do anything - otherwise long content widens the box
  instead of ellipsising. See `.user-identity` in `dashboard.css`.

- The layout is driven by `data-kt-app-*` attributes on `<body>` in
  `templates/dashboard/base.html`, read by `scripts.bundle.js` on DOM ready.
  Removing them breaks the sidebar.
- demo29 inverts the usual Bootstrap palette: `--bs-primary` is **green**
  (`#17C653`) and `--bs-success` is **blue** (`#1B84FF`). Pick badge and button
  modifiers by looking, not by assuming.

Charts follow the Metronic convention - an empty `<div>` with a known id, and a
JS module that finds it, reads colours from CSS custom properties and rebuilds
on theme change. See `static/dashboard/js/enquiry-chart.js`. Data reaches it
through `{{ ...|json_script }}` rather than inline interpolation.

**Licensing:** Metronic is commercial software from KeenThemes. Using it in a
delivered project needs a valid license purchased from ThemeForest.

## SEO

Every public page carries a title, meta description, canonical URL and Open
Graph tags. `/sitemap.xml` and `/robots.txt` are generated, and schema.org data
is attached automatically: `LocalBusiness` sitewide, plus `Service`,
`JobPosting`, `Person`, `FAQPage` and breadcrumbs on the pages that have the
detail. Adding a service or vacancy in the dashboard needs no extra step.

`JobPosting` is the one with direct commercial value — it can put vacancies in
Google's jobs experience without paying a job board.

See [Docs/seo.md](Docs/seo.md), including the list of things that still need a
person: Search Console verification, a Google Business Profile, and a 1200×630
share image.

## Deployment

The project ships a `Dockerfile` and serves its own static files through
WhiteNoise, so it runs on any container host without a web server in front.

Step-by-step for Railway, including the two failure modes that cause silent
data loss rather than an error, is in
[Docs/deploy-railway.md](Docs/deploy-railway.md).

Whatever the host, it needs:

- A **persistent volume** for `MEDIA_ROOT` and `PRIVATE_MEDIA_ROOT`. Container
  filesystems are wiped on redeploy, taking every uploaded image and résumé
  with them.
- `TRUST_PROXY_SSL_HEADER=True` wherever TLS terminates at an edge proxy, or
  `SECURE_SSL_REDIRECT` loops forever.
- MySQL's **timezone tables loaded** — see [Docs/mysql.md](Docs/mysql.md).
- Real SMTP settings. The console backend sends nothing.

## Before going live

- Set a generated `SECRET_KEY` and `DEBUG=False` in `.env` (never commit `.env`)
- Move to MySQL — see [Docs/mysql.md](Docs/mysql.md). SQLite locks the whole
  file on write, so it does not hold up under concurrent traffic
- Load MySQL's timezone tables. Without them `CONVERT_TZ` returns `NULL` and
  the dashboard's date-based figures read zero without erroring
- Turn on `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`
  and `SECURE_HSTS_SECONDS` once TLS is terminating in front of the app
- Delete any fixtures left in `backups/` and the old `db.sqlite3` — both hold
  enquiries, consultations and applications in plain text
- Change the `admin` password (`manage.py changepassword admin`) and restore
  the default `AUTH_PASSWORD_VALIDATORS`, which are currently an empty list
- Run `manage.py seed_dashboard --clear` to remove the sample data
- Serve `MEDIA_ROOT` at `MEDIA_URL`, but **never** expose `PRIVATE_MEDIA_ROOT`
- Set a retention policy for applicant resumes
- Populate `ALLOWED_HOSTS`
- Replace the `#` placeholders in `SOCIAL_LINKS` (`pages/content.py`) with the
  real profile URLs
- Swap the placeholder artwork for real photography
- Run `python manage.py collectstatic`
