import tempfile

from decouple import config, Csv
from .base import *

DEBUG = True
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1,10.0.2.2", cast=Csv())

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "TEST": {"NAME": str(Path(tempfile.gettempdir()) / "dibuang_sayang_test.sqlite3")},
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }
}

# Izinkan Flutter Web mengakses Django saat development lokal
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
]

CORS_ALLOW_CREDENTIALS = True