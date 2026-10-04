from django.core.management.base import BaseCommand

from accounts.models import User
from order.models import Order

DEMO_PASSWORD = "demo12345"

USERS = [
    {"username": "pembeli_demo", "role": User.Role.BUYER, "email": "pembeli@demo.test"},
    {"username": "mitra_demo", "role": User.Role.PARTNER, "email": "mitra@demo.test"},
]

ORDERS = [
    ("DEMO0001", 1, 1, Order.Status.PENDING),
    ("DEMO0002", 2, 2, Order.Status.CONFIRMED),
    ("DEMO0003", 3, 1, Order.Status.COMPLETED),
    ("DEMO0004", 4, 1, Order.Status.CANCELLED),
]


class Command(BaseCommand):
    help = "Buat akun demo (pembeli & mitra); --orders untuk contoh pesanan."

    def add_arguments(self, parser):
        parser.add_argument("--orders", action="store_true")

    def handle(self, *args, **options):
        users = {}
        for data in USERS:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={"role": data["role"], "email": data["email"]},
            )
            user.set_password(DEMO_PASSWORD)
            user.save()
            users[data["username"]] = user
            self.stdout.write(f"{'dibuat' if created else 'diperbarui'}: {user.username}")

        if options["orders"]:
            buyer = users["pembeli_demo"]
            for kode, box_id, jumlah, status in ORDERS:
                Order.objects.update_or_create(
                    kode_pickup=kode,
                    defaults={"pembeli": buyer, "surprise_box_id": box_id, "jumlah": jumlah, "status": status},
                )
            self.stdout.write(f"{len(ORDERS)} pesanan contoh siap")

        self.stdout.write(self.style.SUCCESS(f"Login dengan password: {DEMO_PASSWORD}"))
