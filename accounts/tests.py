from datetime import datetime
from io import StringIO
from unittest.mock import patch

from authlib.integrations.base_client import OAuthError
from django.core.cache import cache
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings
from django.urls import reverse
from food.models import Restaurant, SurpriseBox
from order.models import Order

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
        cache.clear()
        self.user = User.objects.create_user(username="dyah", password="pass12345")

    def test_register_creates_user(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "newbuyer", "email": "newbuyer@example.com",
            "role": User.Role.BUYER, "password1": "SuperSecret123", "password2": "SuperSecret123",
        })
        self.assertTrue(User.objects.filter(username="newbuyer").exists())
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_register_form_has_no_email_field(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "noemail", "email": "victim@example.com",
            "role": User.Role.BUYER, "password1": "SuperSecret123", "password2": "SuperSecret123",
        })
        self.assertEqual(User.objects.get(username="noemail").email, "")

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
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_sets_last_login_cookie_and_logout_deletes_it(self):
        response = self.client.post(reverse("accounts:login"), {"username": "dyah", "password": "pass12345"})
        self.assertIn("last_login", response.cookies)
        raw = self.client.cookies["last_login"].value
        profile = self.client.get(reverse("accounts:profile"))
        self.assertContains(profile, datetime.strptime(raw, "%Y-%m-%dT%H:%M").strftime("%d-%m-%Y %H:%M WIB"))
        self.assertNotContains(profile, raw)
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.cookies["last_login"].value, "")

    def test_profile_ignores_tampered_last_login_cookie(self):
        self.client.login(username="dyah", password="pass12345")
        self.client.cookies["last_login"] = "<script>x</script>"
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>x</script>")

    def test_logout_rejects_get(self):
        self.client.login(username="dyah", password="pass12345")
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


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


class ProfileViewTest(TestCase):
    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)

    def test_shows_role_and_username(self):
        User.objects.create_user(username="mitra9", password="pass12345", role=User.Role.PARTNER)
        self.client.login(username="mitra9", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "mitra9")
        self.assertContains(response, "Mitra Restoran")


class RateLimitTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="dyah", password="pass12345")
        self.url = reverse("accounts:login")
        self.wrong = {"username": "dyah", "password": "salah"}

    def tearDown(self):
        cache.clear()

    def test_login_blocked_after_limit(self):
        for _ in range(10):
            self.assertEqual(self.client.post(self.url, self.wrong).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.wrong).status_code, 429)

    def test_correct_password_also_blocked_after_limit(self):
        for _ in range(10):
            self.client.post(self.url, self.wrong)
        response = self.client.post(self.url, {"username": "dyah", "password": "pass12345"})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_is_never_limited(self):
        for _ in range(15):
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_ip_not_affected(self):
        for _ in range(11):
            self.client.post(self.url, self.wrong, REMOTE_ADDR="10.0.0.1")
        self.assertEqual(self.client.post(self.url, self.wrong, REMOTE_ADDR="10.0.0.2").status_code, 200)

    def test_forwarded_header_first_ip_is_used(self):
        for _ in range(11):
            self.client.post(self.url, self.wrong, HTTP_X_FORWARDED_FOR="1.1.1.1, 9.9.9.9")
        blocked = self.client.post(self.url, self.wrong, HTTP_X_FORWARDED_FOR="1.1.1.1, 8.8.8.8")
        self.assertEqual(blocked.status_code, 429)

    def test_register_blocked_after_limit(self):
        url = reverse("accounts:register")
        for _ in range(10):
            self.client.post(url, {})
        self.assertEqual(self.client.post(url, {}).status_code, 429)

    def test_login_and_register_have_separate_counters(self):
        for _ in range(10):
            self.client.post(self.url, self.wrong)
        self.assertEqual(self.client.post(reverse("accounts:register"), {}).status_code, 200)


class RateLimitResilienceTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_counter_that_expired_mid_request_restarts_at_one(self):
        with patch("accounts.ratelimit.cache.incr", side_effect=ValueError):
            response = self.client.post(reverse("accounts:login"), {"username": "x", "password": "y"})
        self.assertEqual(response.status_code, 200)


@override_settings(GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="secret")
class GoogleKeysTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_fetched_keys_are_passed_to_oauth_client(self):
        keys = {"keys": [{"kid": "abc"}]}
        with patch("accounts.views.fetch_google_keys", return_value=keys), patch("accounts.views.oauth") as oauth:
            oauth.google.server_metadata = {}
            oauth.google.authorize_access_token.return_value = {"userinfo": GOOGLE_INFO}
            self.client.get(reverse("accounts:google_callback"))
        self.assertEqual(oauth.google.server_metadata["jwks"], keys)


class SeedDemoCommandTest(TestCase):
    def run_seed(self, *args):
        out = StringIO()
        call_command("seed_demo", *args, stdout=out)
        return out.getvalue()

    def make_boxes(self, count=4):
        restaurant = Restaurant.objects.create(nama="Kedai Seed", alamat="Jl. Seed")
        for i in range(1, count + 1):
            SurpriseBox.objects.create(
                id=i, restaurant=restaurant, nama_paket=f"Paket {i}", harga_normal=40000, harga_diskon=20000, stok=5
            )
        return restaurant

    def test_creates_demo_accounts_with_roles_and_password(self):
        output = self.run_seed()
        self.assertTrue(User.objects.get(username="pembeli_demo").is_buyer)
        mitra = User.objects.get(username="mitra_demo")
        self.assertTrue(mitra.is_partner)
        self.assertTrue(mitra.check_password("demo12345"))
        self.assertIn("dibuat: mitra_demo", output)

    def test_second_run_updates_instead_of_duplicating(self):
        self.run_seed()
        output = self.run_seed()
        self.assertEqual(User.objects.filter(username__in=["pembeli_demo", "mitra_demo"]).count(), 2)
        self.assertIn("diperbarui: mitra_demo", output)

    def test_ownerless_restaurants_are_given_to_mitra_demo(self):
        restaurant = self.make_boxes(1)
        self.run_seed()
        restaurant.refresh_from_db()
        self.assertEqual(restaurant.owner.username, "mitra_demo")

    def test_orders_flag_creates_sample_orders_once(self):
        self.make_boxes()
        self.assertIn("4 pesanan contoh siap", self.run_seed("--orders"))
        self.run_seed("--orders")
        self.assertEqual(Order.objects.filter(kode_pickup__startswith="DEMO").count(), 4)

    def test_orders_flag_without_boxes_explains_what_to_do(self):
        self.assertIn("jalankan seed_food dulu", self.run_seed("--orders"))
        self.assertEqual(Order.objects.count(), 0)
