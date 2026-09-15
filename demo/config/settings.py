"""Minimal Django settings for the engine prototype.

Deliberately no database, no auth, no DRF - this exists to drive the astrology
engine from a browser and prove the staged-progress flow end to end.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "prototype-only-not-a-real-secret"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "web",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {}
STATIC_URL = "static/"
USE_TZ = True
TIME_ZONE = "Asia/Kolkata"
