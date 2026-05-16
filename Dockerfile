FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1


WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app && \
    mkdir -p /app/logs && \
    chown -R app:app /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app manage.py ./
COPY --chown=app:app config ./config
COPY --chown=app:app my_app ./my_app
# COPY --chown=app:app templates ./templates

USER app

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
