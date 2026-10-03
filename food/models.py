from django.conf import settings
from django.db import models


class Restaurant(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="restaurants",
        null=True,
        blank=True,
    )
    nama = models.CharField(max_length=255)
    alamat = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    jam_buka = models.TimeField(null=True, blank=True)
    jam_tutup = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nama"]

    def __str__(self):
        return self.nama


class SurpriseBox(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="surprise_boxes",
    )
    nama_paket = models.CharField(max_length=255)
    harga_normal = models.DecimalField(max_digits=12, decimal_places=2)
    harga_diskon = models.DecimalField(max_digits=12, decimal_places=2)
    stok = models.PositiveIntegerField(default=0)
    pickup_start = models.DateTimeField(null=True, blank=True)
    pickup_end = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.nama_paket} ({self.restaurant.nama})"

    @property
    def diskon_persen(self):
        if self.harga_normal and self.harga_normal > 0:
            return round((self.harga_normal - self.harga_diskon) / self.harga_normal * 100)
        return 0

