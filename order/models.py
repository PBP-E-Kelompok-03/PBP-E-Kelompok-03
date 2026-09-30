from django.db import models
from django.conf import settings

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    pembeli = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    # TODO: ganti jadi FK ke food.SurpriseBox 
    # sekarang masih ke id surprise_box di fixtures/dummy_data.json
    surprise_box_id = models.PositiveIntegerField()
    jumlah = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    kode_pickup = models.CharField(max_length=20, unique=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.kode_pickup} ({self.status})"
