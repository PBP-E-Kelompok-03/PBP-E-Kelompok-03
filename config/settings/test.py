import tempfile

from .base import *

DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3.test",
        "TEST": {"NAME": str(Path(tempfile.gettempdir()) / "dibuang_sayang_test.sqlite3")},
        "OPTIONS": {"timeout": 20},
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
