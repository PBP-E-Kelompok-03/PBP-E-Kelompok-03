import requests
from django.core.cache import cache

JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
FRESH_KEY = "google:jwks"
STALE_KEY = "google:jwks:stale"
FRESH_TTL = 60 * 60
STALE_TTL = 60 * 60 * 24


def fetch_google_keys():
    """ambil key public google, pakai cache supaya tidak request terus"""
    keys = cache.get(FRESH_KEY)
    if keys is not None:
        return keys
    try:
        response = requests.get(JWKS_URI, timeout=5)
        response.raise_for_status()
        keys = response.json()
    except (requests.RequestException, ValueError):
        return cache.get(STALE_KEY)
    cache.set(FRESH_KEY, keys, FRESH_TTL)
    cache.set(STALE_KEY, keys, STALE_TTL)
    return keys
