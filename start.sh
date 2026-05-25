#!/usr/bin/env bash
set -euo pipefail

# Wait for the database to accept connections. This matters when the app
# and Postgres boot at the same time (e.g. a Coolify project restart);
# otherwise migrate would fail with a connection error.
echo "Waiting for database..."
attempts=0
until python manage.py shell -c "from django.db import connection; connection.ensure_connection()" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 24 ]; then
        echo "Database not reachable after 2 minutes, giving up." >&2
        exit 1
    fi
    sleep 5
done
echo "Database ready."

python manage.py migrate --noinput

# Load the 1000-word vocabulary once (skips if chapters already exist).
python manage.py import_1000_words

python manage.py collectstatic --noinput

# Kick off the audio backfill in the background so the deploy doesn't wait
# on Cartesia. Logs land in the regular container output.
# Safe to run repeatedly: only cards/letters with missing recordings get hit.
python manage.py generate_audio --sleep 0.1 &

exec gunicorn kartuli.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --access-logfile - \
    --error-logfile -
