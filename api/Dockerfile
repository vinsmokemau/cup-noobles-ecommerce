# Local development image (T1.6). T20.1 adds the production stage.
FROM python:3.12-slim

ARG SUPERCRONIC_VERSION=v0.2.50
ARG SUPERCRONIC_SHA256=d2d7c97fbfefc763d5bbcbbb3f8d61f9dd3410ce5d05a737c414994b80b8cdd0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

# supercronic runs infra/crontab in the scheduler service (§4.8).
ADD --checksum=sha256:${SUPERCRONIC_SHA256} \
    https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64 \
    /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

RUN pip install --no-cache-dir uv==0.13.4

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
