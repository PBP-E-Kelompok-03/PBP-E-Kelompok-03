from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    class Role(models.TextChoices):
        BUYER = "buyer", "Pembeli"
        PARTNER = "partner", "Mitra Restoran"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.BUYER)

    @property
    def is_buyer(self):
        """true kalau role pembeli"""
        return self.role == self.Role.BUYER

    @property
    def is_partner(self):
        """true kalau role mitra restoran"""
        return self.role == self.Role.PARTNER