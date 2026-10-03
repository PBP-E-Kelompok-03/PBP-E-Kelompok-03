import datetime
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from food.models import Restaurant, SurpriseBox


class Command(BaseCommand):
    help = "Seed database with restaurants and surprise boxes from fixtures/dummy_data.json"

    def handle(self, *args, **options):
        fixture_path = Path(settings.BASE_DIR) / "fixtures" / "dummy_data.json"
        if not fixture_path.exists():
            self.stdout.write(self.style.ERROR(f"File {fixture_path} not found."))
            return

        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)

        restaurants_data = data.get("restaurants", [])
        surprise_boxes_data = data.get("surprise_boxes", [])

        now = timezone.localtime()
        today = now.date()

        restaurant_objs = {}
        for item in restaurants_data:
            jam_buka = None
            if item.get("jam_buka"):
                try:
                    jam_buka = datetime.datetime.strptime(item["jam_buka"], "%H:%M").time()
                except ValueError:
                    pass

            jam_tutup = None
            if item.get("jam_tutup"):
                try:
                    jam_tutup = datetime.datetime.strptime(item["jam_tutup"], "%H:%M").time()
                except ValueError:
                    pass

            restaurant, _ = Restaurant.objects.update_or_create(
                id=item["id"],
                defaults={
                    "nama": item.get("nama", ""),
                    "alamat": item.get("alamat", ""),
                    "lat": item.get("lat"),
                    "lng": item.get("lng"),
                    "jam_buka": jam_buka,
                    "jam_tutup": jam_tutup,
                    "is_active": item.get("is_active", True),
                },
            )
            restaurant_objs[restaurant.id] = restaurant

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(restaurant_objs)} restaurants."))

        created_boxes = 0
        for item in surprise_boxes_data:
            restaurant_id = item.get("restaurant_id")
            restaurant = restaurant_objs.get(restaurant_id)
            if not restaurant:
                continue

            pickup_start = None
            if item.get("pickup_start"):
                try:
                    t_start = datetime.datetime.strptime(item["pickup_start"], "%H:%M").time()
                    pickup_start = timezone.make_aware(datetime.datetime.combine(today, t_start))
                except ValueError:
                    pass

            pickup_end = None
            if item.get("pickup_end"):
                try:
                    t_end = datetime.datetime.strptime(item["pickup_end"], "%H:%M").time()
                    pickup_end = timezone.make_aware(datetime.datetime.combine(today, t_end))
                except ValueError:
                    pass

            SurpriseBox.objects.update_or_create(
                id=item["id"],
                defaults={
                    "restaurant": restaurant,
                    "nama_paket": item.get("nama_paket", ""),
                    "harga_normal": item.get("harga_normal", 0),
                    "harga_diskon": item.get("harga_diskon", 0),
                    "stok": item.get("stok", 0),
                    "pickup_start": pickup_start,
                    "pickup_end": pickup_end,
                    "is_active": item.get("is_active", True),
                },
            )
            created_boxes += 1

        self.stdout.write(self.style.SUCCESS(f"Loaded {created_boxes} surprise boxes successfully."))
