import datetime
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import User
from food.models import Restaurant, SurpriseBox


def parse_time(value):
    try:
        return datetime.datetime.strptime(value, "%H:%M").time() if value else None
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Seed restaurants and surprise boxes from fixtures/dummy_data.json"

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true", help="Lewati jika sudah ada restoran.")

    def handle(self, *args, **options):
        if options["if_empty"] and Restaurant.objects.exists():
            self.stdout.write("Data restoran sudah ada, seed dilewati.")
            return

        fixture_path = Path(settings.BASE_DIR) / "fixtures" / "dummy_data.json"
        if not fixture_path.exists():
            self.stdout.write(self.style.ERROR(f"File {fixture_path} not found."))
            return

        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)

        owner, created = User.objects.get_or_create(
            username="mitra_demo",
            defaults={"role": User.Role.PARTNER, "email": "mitra@demo.test"},
        )
        if created:
            owner.set_unusable_password()
            owner.save(update_fields=["password"])

        restaurants = {}
        for item in data.get("restaurants", []):
            restaurant, _ = Restaurant.objects.update_or_create(
                id=item["id"],
                defaults={
                    "owner": owner,
                    "nama": item.get("nama", ""),
                    "alamat": item.get("alamat", ""),
                    "lat": item.get("lat"),
                    "lng": item.get("lng"),
                    "jam_buka": parse_time(item.get("jam_buka")),
                    "jam_tutup": parse_time(item.get("jam_tutup")),
                    "is_active": item.get("is_active", True),
                },
            )
            restaurants[restaurant.id] = restaurant
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(restaurants)} restaurants."))

        boxes = 0
        for item in data.get("surprise_boxes", []):
            restaurant = restaurants.get(item.get("restaurant_id"))
            if not restaurant:
                continue
            SurpriseBox.objects.update_or_create(
                id=item["id"],
                defaults={
                    "restaurant": restaurant,
                    "nama_paket": item.get("nama_paket", ""),
                    "harga_normal": item.get("harga_normal", 0),
                    "harga_diskon": item.get("harga_diskon", 0),
                    "stok": item.get("stok", 0),
                    "is_active": item.get("is_active", True),
                },
            )
            boxes += 1
        self.stdout.write(self.style.SUCCESS(f"Loaded {boxes} surprise boxes successfully."))
