release: python manage.py migrate --noinput
web: gunicorn kartuli.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --access-logfile - --error-logfile -
