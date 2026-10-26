from unittest.mock import patch

from authlib.integrations.base_client import OAuthError
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import User

class UserModelTest(TestCase):
    def test_default_role_is_buyer(self):
        user = User.objects.create_user(username="buyer1", password="pass12345")
        self.assertTrue(user.is_buyer)

    def test_partner_role(self):
        user = User.objects.create_user(username="partner1", password="pass12345", role=User.Role.PARTNER)
        self.assertTrue(user.is_partner)

class AuthViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dyah", password="pass12345")

    def test_register_creates_user(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "newbuyer", "email": "newbuyer@example.com",
            "role": User.Role.BUYER, "password1": "SuperSecret123", "password2": "SuperSecret123",
        })
        self.assertTrue(User.objects.filter(username="newbuyer").exists())

    def test_login_success(self):
        response = self.client.post(reverse("accounts:login"), {"username": "dyah", "password": "pass12345"})
        self.assertEqual(response.status_code, 302)

    def test_login_wrong_password_fails(self):
        response = self.client.post(reverse("accounts:login"), {"username": "dyah", "password": "wrongpass"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_unknown_username_fails(self):
        response = self.client.post(reverse("accounts:login"), {"username": "notexist", "password": "pass12345"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_register_duplicate_username_fails(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "dyah", "email": "dupe@example.com",
            "role": User.Role.BUYER, "password1": "SuperSecret123", "password2": "SuperSecret123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="dyah").count(), 1)

    def test_register_password_mismatch_fails(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "mismatchuser", "email": "mismatch@example.com",
            "role": User.Role.BUYER, "password1": "SuperSecret123", "password2": "DifferentPass456",
        })
        self.assertFalse(User.objects.filter(username="mismatchuser").exists())

    def test_authenticated_user_redirected_from_register(self):
        self.client.login(username="dyah", password="pass12345")
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 302)

    def test_logout(self):
        self.client.login(username="dyah", password="pass12345")
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)


GOOGLE_INFO = {"sub": "12345", "email": "dyah@example.com", "email_verified": True, "name": "Dyah Z"}


@override_settings(GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="secret")
class GoogleOAuthTest(TestCase):
    def setUp(self):
        cache.clear()

    def callback(self, info=None, error=None):
        with patch("accounts.views.fetch_google_keys", return_value=None), patch("accounts.views.oauth") as oauth:
            client = oauth.google
            if error:
                client.authorize_access_token.side_effect = error
            else:
                client.authorize_access_token.return_value = {"userinfo": info if info is not None else GOOGLE_INFO}
            return self.client.get(reverse("accounts:google_callback"))

    def test_login_page_shows_google_button_when_configured(self):
        self.assertContains(self.client.get(reverse("accounts:login")), "Masuk dengan Google")

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    def test_login_page_hides_google_button_when_not_configured(self):
        self.assertNotContains(self.client.get(reverse("accounts:login")), "Masuk dengan Google")

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    def test_google_login_not_configured_redirects_to_login(self):
        response = self.client.get(reverse("accounts:google_login"))
        self.assertRedirects(response, reverse("accounts:login"))

    def test_google_login_redirects_to_provider(self):
        with patch("accounts.views.oauth") as oauth:
            oauth.google.authorize_redirect.return_value = HttpResponseRedirect("https://accounts.google.com/auth")
            response = self.client.get(reverse("accounts:google_login"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(oauth.google.authorize_redirect.call_args[0][1].endswith("/accounts/google/callback/"))

    def test_callback_creates_user_and_logs_in(self):
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="google_12345")
        self.assertEqual(user.email, "dyah@example.com")
        self.assertEqual(user.first_name, "Dyah Z")
        self.assertEqual(user.role, User.Role.BUYER)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_callback_reuses_existing_google_user(self):
        self.callback()
        self.client.logout()
        self.callback()
        self.assertEqual(User.objects.filter(username="google_12345").count(), 1)
        self.assertIn("_auth_user_id", self.client.session)

    def test_callback_rejects_email_used_by_other_account(self):
        User.objects.create_user(username="dyah", email="DYAH@example.com", password="pass12345")
        response = self.callback()
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertFalse(User.objects.filter(username="google_12345").exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_callback_rejects_unverified_email(self):
        response = self.callback({**GOOGLE_INFO, "email_verified": False})
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertFalse(User.objects.filter(username="google_12345").exists())

    def test_callback_rejects_missing_sub(self):
        response = self.callback({"email": "a@example.com", "email_verified": True})
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(User.objects.count(), 0)

    def test_callback_oauth_error_redirects_to_login(self):
        response = self.callback(error=OAuthError(error="access_denied"))
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(User.objects.count(), 0)

    def test_navbar_shows_full_name(self):
        self.callback()
        self.assertContains(self.client.get(reverse("order:history")), "Dyah Z")
