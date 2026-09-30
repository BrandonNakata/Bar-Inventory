# Home Assistant add-on image. Requirements install before the code is copied, for layer caching.

# Debian, not Alpine: prebuilt wheels install on glibc; musl would compile them on the Pi.
FROM docker.io/library/python:3.12-slim-bookworm

# openssl: run.sh uses it once, to make the self-signed HTTPS certificate.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY static ./static
COPY run.sh /run.sh

# Strip Windows line endings from run.sh.
RUN sed -i 's/\r$//' /run.sh && chmod +x /run.sh

# BAR_DB_PATH on /data survives updates and is included in Home Assistant backups.
ENV BAR_DB_PATH=/data/bar.db \
    BAR_STATIC_DIR=/app/static \
    PYTHONUNBUFFERED=1

CMD ["/run.sh"]
