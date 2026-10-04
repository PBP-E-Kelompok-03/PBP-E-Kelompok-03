import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from food.models import Restaurant, SurpriseBox
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
        parser.add_argument("--open-window", action="store_true", help="Buka jendela pickup box demo selama 4 jam dari sekarang.")

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

        mitra = users["mitra_demo"]
        owned = Restaurant.objects.filter(surprise_boxes__id__in=[o[1] for o in ORDERS], owner__isnull=True)
        owned.update(owner=mitra)

        if options["open_window"]:
            now = timezone.now()
            SurpriseBox.objects.filter(pk__in=[o[1] for o in ORDERS]).update(
                pickup_start=now - datetime.timedelta(hours=1),
                pickup_end=now + datetime.timedelta(hours=4),
                is_active=True,
            )
            self.stdout.write("jendela pickup box demo dibuka")

        if options["orders"]:
            buyer = users["pembeli_demo"]
            created = 0
            for kode, box_id, jumlah, status in ORDERS:
                box = SurpriseBox.objects.filter(pk=box_id).first()
                if not box:
                    continue
                Order.objects.update_or_create(
                    kode_pickup=kode,
                    defaults={"pembeli": buyer, "surprise_box": box, "jumlah": jumlah, "status": status},
                )
                created += 1
            self.stdout.write(f"{created} pesanan contoh siap" if created else "Box belum ada, jalankan seed_food dulu")

        self.stdout.write(self.style.SUCCESS(f"Login dengan password: {DEMO_PASSWORD}"))
