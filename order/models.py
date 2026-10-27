import datetime

from django.db import models
from django.conf import settings

ORDER_TTL = datetime.timedelta(hours=24)


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    pembeli = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    surprise_box = models.ForeignKey(
        "food.SurpriseBox",
        null=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    jumlah = models.PositiveIntegerField()
    harga_satuan = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    kode_pickup = models.CharField(max_length=20, unique=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pembeli", "surprise_box"],
                condition=models.Q(status__in=["pending", "confirmed"]),
                name="uniq_active_order_per_box",
            )
        ]

    @property
    def kedaluwarsa_pada(self):
        return self.dibuat_pada + ORDER_TTL

    def __str__(self):
        return f"Order {self.kode_pickup} ({self.status})"
