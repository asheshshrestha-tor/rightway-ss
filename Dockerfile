# Railway will use this in preference to its own builder detection.
#
# A Dockerfile rather than Nixpacks because `mysqlclient` is a C extension: it
# needs the MySQL client headers and a compiler at build time, which is the
# usual first thing to fail on a default Python builder. Here they are explicit.

FROM python:3.12-slim

# Faster startup and unbuffered logs, so Railway's log view shows output as it
# happens rather than in blocks when the buffer flushes.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Hashed filenames plus pre-compressed variants. Set here rather than in
# settings so a fresh clone can run the tests without collectstatic first, and
# so the manifest is built by the same image that serves it.
ENV STATICFILES_BACKEND=whitenoise.storage.CompressedManifestStaticFilesStorage

WORKDIR /app

# `default-libmysqlclient-dev` supplies both the headers to build against and
# the shared library loaded at runtime, so it has to stay in the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copied on its own so the dependency layer is only rebuilt when requirements
# change, not on every edit to the application.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run at build time so a broken static file fails the build rather than the
# site. No database is touched, so the default SQLite setting is irrelevant here.
RUN python manage.py collectstatic --noinput

# Uploads live on a mounted volume in production. These are the fallback paths
# for running the image without one; anything written here is lost on redeploy.
RUN mkdir -p /app/media /app/private-media

EXPOSE 8000

# `migrate` runs on every boot: applying nothing is a no-op, so it is safe to
# repeat, and it means a deploy carrying a new migration needs no manual step.
# Keep this to a single replica - concurrent boots would race on migrate.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 60 --access-logfile - --error-logfile -"]
