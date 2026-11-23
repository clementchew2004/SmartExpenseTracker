# The API packed as a container image, the "recipe" Render builds and runs.
#
# Try it on your Mac (from the repo root):
#   docker build -t expenses-api backend
#   docker run --rm -p 8001:8000 --env-file backend/.env \
#     -e DATABASE_URL=postgresql+psycopg://expenses:expenses@host.docker.internal:5432/expenses \
#     expenses-api
# then open http://localhost:8001/health

# Start from a small Linux with Python 3.13 already installed.
FROM python:3.13-slim

# Don't write .pyc files; print log lines straight away instead of buffering them,
# so they show up in Render's log viewer as they happen.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Libraries first, in their own step: Docker reuses this slow step on the next
# build as long as requirements.txt hasn't changed, so code-only deploys are quick.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then the code. Secrets are NOT copied in (.dockerignore leaves out .env):
# in production they come from Render's Environment settings.
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Run as an ordinary user, not root: if the app were ever broken into, the
# attacker wouldn't be the container's administrator.
RUN useradd --create-home appuser
USER appuser

# Bring the database up to date, then start the API. If a migration fails, the
# API never starts, Render's health check (/health) fails, and Render keeps the
# previous version running. Render tells the app which port to use in $PORT.
# `exec` makes the API take over from the shell, so when Render asks it to stop
# (on every redeploy) the API itself hears it and shuts down cleanly.
CMD ["sh", "-c", "alembic upgrade head && exec fastapi run app/main.py --host 0.0.0.0 --port ${PORT:-8000}"]
