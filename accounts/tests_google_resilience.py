from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import google
from .models import User

KEYS = {"keys": [{"kid": "abc", "kty": "RSA"}]}


class GoogleKeysCacheTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("accounts.google.requests.get")
    def test_keys_fetched_once_then_served_from_cache(self, get):
        get.return_value.json.return_value = KEYS
        self.assertEqual(google.fetch_google_keys(), KEYS)
        self.assertEqual(google.fetch_google_keys(), KEYS)
        self.assertEqual(get.call_count, 1)

    @patch("accounts.google.requests.get")
    def test_uses_stale_keys_when_google_is_down(self, get):
        get.return_value.json.return_value = KEYS
        google.fetch_google_keys()
        cache.delete(google.FRESH_KEY)
        get.side_effect = requests.ConnectionError()
        self.assertEqual(google.fetch_google_keys(), KEYS)

    @patch("accounts.google.requests.get", side_effect=requests.Timeout())
    def test_returns_none_when_google_down_and_nothing_cached(self, get):
        self.assertIsNone(google.fetch_google_keys())


@override_settings(GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="secret")
class GoogleCallbackResilienceTest(TestCase):
    def setUp(self):
        cache.clear()

    def callback(self, error):
        with patch("accounts.views.fetch_google_keys", return_value=None), patch("accounts.views.oauth") as oauth:
            oauth.google.authorize_access_token.side_effect = error
            return self.client.get(reverse("accounts:google_callback"), follow=True)

    def test_connection_error_shows_message_instead_of_500(self):
        response = self.callback(requests.ConnectionError())
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertContains(response, "Google")
        self.assertEqual(User.objects.count(), 0)

    def test_timeout_shows_message_instead_of_500(self):
        response = self.callback(requests.Timeout())
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(User.objects.count(), 0)
