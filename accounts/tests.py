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
        
