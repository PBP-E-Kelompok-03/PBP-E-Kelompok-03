from django.test import TestCase
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
