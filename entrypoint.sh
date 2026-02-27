#!/bin/sh

# Exit immediately if any command fails
set -e

# ── Wait for Postgres ──────────────────────────────────────────────────────────
# Django will crash on startup if Postgres isn't ready yet.
# This loop retries every second until the port is open.
# echo "Waiting for Postgres..."
# while ! nc -z $DB_HOST $DB_PORT; do
#   sleep 1
# done
# echo "Postgres is ready."
#
# # ── Wait for Redis ─────────────────────────────────────────────────────────────
# echo "Waiting for Redis..."
# while ! nc -z $REDIS_HOST $REDIS_PORT; do
#   sleep 1
# done
# echo "Redis is ready."

# ── Run as app or worker ───────────────────────────────────────────────────────
# The same image is used for both the Django app and the Celery worker.
# Docker Compose passes a CMD to tell the container which role to play.
# This keeps things simple — one image, two roles.

if [ "$1" = "worker" ]; then
  echo "Starting Celery worker..."
  exec celery -A core worker --loglevel=info

else
#   echo "Running migrations..."
#   python manage.py migrate --noinput

  echo "Starting Gunicorn..."
  exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
fi
