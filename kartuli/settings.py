"""
Django settings for kartuli project.

Configured to read environment variables so it can be deployed
on Coolify (or any container/PaaS host) with sane defaults for
local development.
"""

from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from dotenv import load_dotenv
import os


BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a local .env file if present (ignored in production).
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-in-production",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DJANGO_DEBUG", default=False)


def _coolify_urls() -> list[str]:
    """Read Coolify's auto-injected URL env vars (comma-separated)."""
    raw = os.environ.get("COOLIFY_URL", "")
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


def _coolify_hosts() -> list[str]:
    """Hostnames derived from COOLIFY_URL plus COOLIFY_FQDN (already host-only)."""
    hosts = [urlparse(u).hostname for u in _coolify_urls()]
    fqdn_raw = os.environ.get("COOLIFY_FQDN", "")
    hosts += [h.strip() for h in fqdn_raw.split(",") if h.strip()]
    return [h for h in hosts if h]


# Default to accepting any Host header. Coolify's reverse proxy is the only
# thing that can reach the container, so this is effectively scoped to the
# domains you've routed to the app. Override with DJANGO_ALLOWED_HOSTS
# (comma-separated) if you want to tighten it.
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=_coolify_hosts() or ["*"],
)

# Always permit loopback so the container's internal healthcheck
# (Docker HEALTHCHECK / Coolify probe hitting http://127.0.0.1:$PORT/healthz)
# is accepted regardless of which public host is configured.
if "*" not in ALLOWED_HOSTS:
    for _loopback in ("localhost", "127.0.0.1"):
        if _loopback not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_loopback)

# CSRF needs explicit trusted origins for POSTs over HTTPS (admin, our quiz
# answer endpoint, etc.). Auto-derive from Coolify's COOLIFY_URL when present,
# and additionally from any non-wildcard ALLOWED_HOSTS as a fallback.
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=list(
        dict.fromkeys(  # de-duplicate while preserving order
            _coolify_urls()
            + [
                f"https://{host}"
                for host in ALLOWED_HOSTS
                if host not in {"*", "localhost", "127.0.0.1"}
            ]
        )
    ),
)


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "flashcards",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "kartuli.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "kartuli.wsgi.application"


# Database
# Defaults to local sqlite; set DATABASE_URL in production (e.g. Postgres on Coolify).

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (served via WhiteNoise in production).
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (uploads).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Behind a TLS-terminating proxy (Coolify/Traefik) – respect the forwarded
# protocol header and enable secure cookies in production.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
    )
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}
