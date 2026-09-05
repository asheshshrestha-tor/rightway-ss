"""Django settings.

Anything that differs between machines - secrets, the database, mail, debug -
comes from the environment, read from a `.env` file in the project root. See
`.env.example` for the full list; copy it to `.env` and fill it in.

Defaults are chosen so the project still runs with no `.env` at all (SQLite,
console email), which keeps a fresh clone working before anything is configured.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CONN_MAX_AGE=(int, 60),
    EMAIL_PORT=(int, 587),
    EMAIL_USE_TLS=(bool, True),
)

# Real environment variables win over the file, so a hosting panel or a
# systemd unit can override anything without editing files on disk.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Generates /sitemap.xml from pages/sitemaps.py.
    "django.contrib.sitemaps",
    "pages",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves everything in STATIC_ROOT straight from the app process. Platforms
    # like Railway put no web server in front, so without this the CSS, the
    # Metronic bundle and the logo all 404 as soon as DEBUG is False.
    # Must sit directly after SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pages.context_processors.site",
                "dashboard.navigation.context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database --------------------------------------------------------------
# DATABASE_URL drives everything, e.g.
#   mysql://rightway:secret@127.0.0.1:3306/rightway
#   sqlite:///db.sqlite3
DATABASES = {
    "default": env.db_url(
        "DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # `sqlite:///db.sqlite3` parses to a path relative to the working
    # directory, which would silently create a second, empty database if the
    # app is ever started from somewhere else. Anchor it to the project.
    name = Path(DATABASES["default"]["NAME"])
    if not name.is_absolute():
        DATABASES["default"]["NAME"] = str(BASE_DIR / name)

if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].update(
        {
            # utf8mb4 is the only charset that stores the full Unicode range -
            # names with accents, and emoji in an enquiry message.
            "charset": "utf8mb4",
            # Without strict mode MySQL silently truncates oversized values
            # instead of raising, so bad data lands in the table unnoticed.
            "sql_mode": "STRICT_TRANS_TABLES",
        }
    )
    # Reuse connections rather than opening one per request.
    DATABASES["default"]["CONN_MAX_AGE"] = env("CONN_MAX_AGE")
    DATABASES["default"]["TEST"] = {
        "CHARSET": "utf8mb4",
        "COLLATION": "utf8mb4_unicode_ci",
    }

# Enforced when a password is set through a form - the dashboard's change and
# reset pages. Existing passwords are unaffected until they are next changed.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-au"
TIME_ZONE = "Australia/Brisbane"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- File storage ----------------------------------------------------------
# Uploads go to S3 in production and to the filesystem everywhere else. Off by
# default so a fresh clone, the test suite and local development all run with
# no AWS account involved.
USE_S3 = env.bool("USE_S3", default=False)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Resumes. A named backend of its own rather than another folder under
    # "default", because the two have opposite rules: everything in "default"
    # is world-readable by design, and nothing in "private" ever may be.
    "private": {"BACKEND": "pages.vacancy_models.PrivateMediaStorage"},
    # The manifest backend hashes every filename, so a CSS change reaches
    # visitors immediately instead of waiting out a cached copy, and
    # "Compressed" pre-builds the gzip/brotli variants. It is opt-in because it
    # refuses to resolve a static file until `collectstatic` has written the
    # manifest - which would make the test suite fail on a fresh clone. The
    # Dockerfile turns it on for production.
    #
    # Static files stay here even with USE_S3 on. WhiteNoise already serves
    # them from the app process under hashed, far-future-cacheable names, so
    # putting them in a bucket would add cost and a deploy step to buy nothing.
    "staticfiles": {
        "BACKEND": env(
            "STATICFILES_BACKEND",
            default="django.contrib.staticfiles.storage.StaticFilesStorage",
        )
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")

# Uploaded resumes are personal information and must never be reachable by
# guessing a URL. On the filesystem they live outside MEDIA_ROOT; on S3 they
# live in a different bucket entirely. Either way the only way to read one is
# `dashboard.careers_views.application_resume`, which checks permissions.
PRIVATE_MEDIA_ROOT = env.path("PRIVATE_MEDIA_ROOT", default=BASE_DIR / "private-media")

# Uploaded images have to be served by something. On a container host there is
# no web server in front, so Django does it - see config/urls.py. With USE_S3
# the bucket does it instead and this turns itself off; leaving it off with
# nothing in front means every uploaded logo and photo 404s. It never exposes
# PRIVATE_MEDIA_ROOT, which is a separate directory reached only through a
# permission-checked view.
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=not USE_S3)

if USE_S3:
    # Sydney by default: it is the closest region to the people using this
    # site, and resumes are personal information that is better kept onshore.
    _AWS = {
        "access_key": env("AWS_ACCESS_KEY_ID"),
        "secret_key": env("AWS_SECRET_ACCESS_KEY"),
        "region_name": env("AWS_S3_REGION_NAME", default="ap-southeast-2"),
        "signature_version": "s3v4",
        # Without this boto3 builds URLs against the legacy global endpoint,
        # `bucket.s3.amazonaws.com`, and every request to a bucket outside
        # us-east-1 pays a 307 redirect to the regional one before it can be
        # answered. "virtual" addresses the region directly. Path style is the
        # other option and is deprecated.
        "addressing_style": "virtual",
        # Both buckets have ACLs disabled ("Bucket owner enforced", which is
        # the default for new buckets). Sending an ACL with an upload would be
        # rejected outright, so do not set one.
        "default_acl": None,
        # What FileSystemStorage already does: a second upload of the same name
        # is stored beside the first under a suffix, rather than overwriting a
        # file that some other row still points at.
        "file_overwrite": False,
    }

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_AWS,
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
            "location": "media",
            # Unsigned, so the URL of a logo is stable and every cache between
            # the bucket and the visitor can keep it. Signing would put an
            # expiring query string on every <img> src, which busts all of them
            # and turns each page view back into a billed request.
            "querystring_auth": False,
            # A CloudFront domain in front of the bucket, when there is one.
            "custom_domain": env("AWS_S3_CUSTOM_DOMAIN", default=""),
            # Safe to cache forever because nothing is ever overwritten in
            # place: file_overwrite is off, so a replacement gets a new name
            # and the old URL simply stops being referenced.
            "object_parameters": {
                "CacheControl": env(
                    "AWS_MEDIA_CACHE_CONTROL",
                    default="public, max-age=31536000, immutable",
                )
            },
        },
    }

    STORAGES["private"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_AWS,
            "bucket_name": env("AWS_PRIVATE_STORAGE_BUCKET_NAME"),
            # Signed and short-lived, and explicitly never routed through the
            # public CDN even if one is configured above.
            "querystring_auth": True,
            "querystring_expire": env.int("AWS_PRIVATE_URL_EXPIRY", default=300),
            "custom_domain": None,
        },
    }

# Applicants upload documents, not archives or executables.
RESUME_ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt"]
RESUME_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth ------------------------------------------------------------------
# The staff dashboard at /dashboard/ replaces Django's admin as the primary
# back office, so auth redirects point there rather than at /admin/.
LOGIN_URL = "dashboard:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "dashboard:login"

# --- Email -----------------------------------------------------------------
# Defaults to the console backend so the contact form works out of the box.
# To send for real, set EMAIL_BACKEND in .env to one of:
#
#   config.ses_backend.SESEmailBackend            Amazon SES over its API
#   django.core.mail.backends.smtp.EmailBackend   any SMTP server
#
# Docs/email.md covers both.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)

# Only read by the SMTP backend.
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# Only read by the SES backend (config/ses_backend.py). The region must be the
# one the sending domain is verified in - SES identities are regional, and a
# client pointed at the wrong region is refused with "email address is not
# verified" even though it is, elsewhere. Sydney by default, to match the
# buckets.
#
# The credentials default to the S3 key pair so one IAM user serves both;
# scripts/aws/iam-policy.json grants it ses:SendEmail. Set the SES-specific
# names only if mail should use a different identity. Empty means "let boto3
# find credentials itself" - an instance or task role on a host that has one.
AWS_SES_REGION_NAME = env(
    "AWS_SES_REGION_NAME",
    default=env("AWS_S3_REGION_NAME", default="ap-southeast-2"),
)
AWS_SES_ACCESS_KEY_ID = env(
    "AWS_SES_ACCESS_KEY_ID", default=env("AWS_ACCESS_KEY_ID", default="")
)
AWS_SES_SECRET_ACCESS_KEY = env(
    "AWS_SES_SECRET_ACCESS_KEY", default=env("AWS_SECRET_ACCESS_KEY", default="")
)
# Optional. An SES configuration set turns on per-message event tracking -
# bounces, complaints, deliveries - in CloudWatch or SNS. Leave empty to send
# without one.
AWS_SES_CONFIGURATION_SET = env("AWS_SES_CONFIGURATION_SET", default="")

DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", default="no-reply@rightwaysupportservices.com.au"
)
# Fallbacks only - the live values are editable in the dashboard under
# Settings, and pages.consultation_mail prefers those.
CONTACT_EMAIL = env("CONTACT_EMAIL", default="arshdeep@rightwaysupportservices.com.au")
CONSULTATION_PHONE = env("CONSULTATION_PHONE", default="0470 522 587")

# Who hears about a submission is worked out from dashboard permissions - see
# pages.notifications.recipients - so staff receive what they can act on
# without anything being listed here. This is only for addresses that have no
# staff account, such as a developer watching submissions during testing.
ADMIN_NOTIFICATION_EMAILS = env.list("ADMIN_NOTIFICATION_EMAILS", default=[])

# Testing safety net. With this set, every outgoing email goes to these
# addresses instead of the real ones, with the intended recipients written into
# the subject and body. The site still works out who *would* have received it,
# so the routing under test is the real thing. Leave empty in production.
EMAIL_REDIRECT_TO = env.list("EMAIL_REDIRECT_TO", default=[])
if EMAIL_REDIRECT_TO:
    EMAIL_REDIRECT_WRAPPED_BACKEND = EMAIL_BACKEND
    EMAIL_BACKEND = "config.email_backend.RedirectingEmailBackend"

# --- HTTPS -----------------------------------------------------------------
# Off by default so local development over http keeps working; turn on in the
# production .env once TLS is terminating in front of the app.

# Platforms like Railway terminate TLS at their edge and forward plain HTTP to
# the app, so Django sees an insecure request and SECURE_SSL_REDIRECT would
# redirect to https forever. This tells it to trust the proxy's own header.
# Only safe when a proxy really is in front and sets the header itself - the
# app must not be reachable directly, or a client could forge it.
if env.bool("TRUST_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
