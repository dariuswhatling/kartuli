# Kartuli

A blank Django 6 project, pre-configured for production deployment on
[Coolify](https://coolify.io/) (or any Docker / Nixpacks PaaS).

## Stack

- Django 6
- Gunicorn (WSGI server)
- WhiteNoise (static file serving)
- `dj-database-url` (SQLite by default, Postgres via `DATABASE_URL`)
- `python-dotenv` (loads a local `.env` for development)

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DJANGO_DEBUG=true and a random DJANGO_SECRET_KEY

python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py runserver
```

Visit http://127.0.0.1:8000/.

A health-check endpoint is available at `/healthz`.

## Project layout

```
.
├── Dockerfile          # Container image used by Coolify
├── Procfile            # Alternative buildpack entrypoint (Nixpacks)
├── start.sh            # Migrates, collects static, then runs gunicorn
├── requirements.txt
├── manage.py
├── kartuli/            # Django project package (settings, urls, wsgi, views)
└── templates/          # Project-level templates (home.html)
```

## Deploying to Coolify

1. Push this repo to GitHub (already configured at
   `git@github.com:dariuswhatling/kartuli.git`).
2. In Coolify, create a new **Application** and connect it to this repository.
3. Build pack: choose **Dockerfile** (recommended — uses the included
   `Dockerfile`). Nixpacks also works and will pick up the `Procfile`.
4. Set the **port** to `8000` (the `Dockerfile` exposes 8000 and `start.sh`
   honours `$PORT`).
5. Set the **health-check path** to `/healthz`.
6. Configure these environment variables in the Coolify UI:

   | Variable | Example | Notes |
   | --- | --- | --- |
   | `DJANGO_SECRET_KEY` | *long random string* | Required. Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
   | `DJANGO_DEBUG` | `false` | Must be `false` in production |
   | `DJANGO_ALLOWED_HOSTS` | `kartuli.example.com` | Comma-separated; include every hostname Coolify routes to the app |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://kartuli.example.com` | Comma-separated full origins (scheme + host) |
   | `DATABASE_URL` | `postgres://user:pass@host:5432/kartuli` | Optional. Omit to keep SQLite; recommended to add a Postgres service in Coolify |
   | `DJANGO_SECURE_SSL_REDIRECT` | `true` | Optional hardening once HTTPS works |
   | `DJANGO_SECURE_HSTS_SECONDS` | `3600` | Optional hardening |

7. Add a persistent volume for the SQLite file (`/app/db.sqlite3`) **only if**
   you stick with SQLite. For real workloads use the Postgres service and set
   `DATABASE_URL`.
8. Deploy. The container runs `start.sh`, which applies migrations, collects
   static files, then starts gunicorn.

### Creating an admin user after deploy

From the Coolify "Terminal" / "Exec" tab on the running container:

```bash
python manage.py createsuperuser
```

## Useful commands

```bash
python manage.py check --deploy   # Production checklist
python manage.py collectstatic    # Manually collect static assets
docker build -t kartuli .         # Test the production image locally
docker run --rm -p 8000:8000 \
  -e DJANGO_SECRET_KEY=dev \
  -e DJANGO_DEBUG=false \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  kartuli
```
