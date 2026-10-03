import datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from food.models import Restaurant, SurpriseBox


class FoodModelTest(TestCase):
    def setUp(self):
        self.partner = User.objects.create_user(
            username="mitra1", password="password123", role="partner"
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.partner,
            nama="Warung Berkah",
            alamat="Jl. Margonda Raya No. 1",
            lat=-6.368,
            lng=106.832,
            jam_buka=datetime.time(8, 0),
            jam_tutup=datetime.time(21, 0),
        )

    def test_restaurant_str(self):
        self.assertEqual(str(self.restaurant), "Warung Berkah")
        self.assertTrue(self.restaurant.is_active)

    def test_surprise_box_diskon_persen(self):
        box = SurpriseBox.objects.create(
            restaurant=self.restaurant,
            nama_paket="Paket Hemat Nasi",
            harga_normal=30000,
            harga_diskon=15000,
            stok=5,
        )
        self.assertEqual(box.diskon_persen, 50)
        self.assertIn("Paket Hemat Nasi", str(box))


class FoodViewsTest(TestCase):
    def setUp(self):
        self.partner = User.objects.create_user(
            username="mitra1", password="password123", role="partner"
        )
        self.other_user = User.objects.create_user(
            username="buyer1", password="password123", role="buyer"
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.partner,
            nama="Bistro Kenari",
            alamat="Jl. Akses UI",
            jam_buka=datetime.time(9, 0),
            jam_tutup=datetime.time(20, 0),
        )
        self.box = SurpriseBox.objects.create(
            restaurant=self.restaurant,
            nama_paket="Paket Roti Spesial",
            harga_normal=40000,
            harga_diskon=20000,
            stok=3,
        )

    def test_food_list_status_code(self):
        response = self.client.get(reverse("food:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paket Roti Spesial")

    def test_food_list_search(self):
        response = self.client.get(reverse("food:list") + "?q=Kenari")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bistro Kenari")

        response_empty = self.client.get(reverse("food:list") + "?q=TidakAdaPasti")
        self.assertEqual(response_empty.status_code, 200)
        self.assertContains(response_empty, "Tidak ada paket Surprise Box")

    def test_restaurant_detail(self):
        response = self.client.get(reverse("food:restaurant_detail", args=[self.restaurant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bistro Kenari")
        self.assertContains(response, "Paket Roti Spesial")

    def test_create_restaurant_requires_login(self):
        response = self.client.get(reverse("food:create_restaurant"))
        self.assertEqual(response.status_code, 302)

    def test_create_restaurant_success(self):
        self.client.login(username="mitra1", password="password123")
        response = self.client.post(
            reverse("food:create_restaurant"),
            {
                "nama": "Resto Baru",
                "alamat": "Jl. Baru No. 12",
                "lat": -6.37,
                "lng": 106.83,
                "jam_buka": "08:00",
                "jam_tutup": "21:00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Restaurant.objects.filter(nama="Resto Baru").exists())

    def test_create_surprise_box_success(self):
        self.client.login(username="mitra1", password="password123")
        response = self.client.post(
            reverse("food:create_surprise_box", args=[self.restaurant.id]),
            {
                "nama_paket": "Paket Sarapan",
                "harga_normal": 25000,
                "harga_diskon": 12500,
                "stok": 4,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SurpriseBox.objects.filter(nama_paket="Paket Sarapan").exists())

    def test_delete_surprise_box_forbidden_for_other_user(self):
        self.client.login(username="buyer1", password="password123")
        response = self.client.post(reverse("food:delete_surprise_box", args=[self.box.id]))
        self.assertEqual(response.status_code, 403)
        self.box.refresh_from_db()
        self.assertTrue(self.box.is_active)

    def test_api_restaurants(self):
        response = self.client.get(reverse("food:api_restaurants"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("restaurants", data)
        self.assertTrue(any(r["nama"] == "Bistro Kenari" for r in data["restaurants"]))

    def test_api_surprise_boxes(self):
        response = self.client.get(reverse("food:api_surprise_boxes"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("surprise_boxes", data)
        self.assertTrue(any(b["nama_paket"] == "Paket Roti Spesial" for b in data["surprise_boxes"]))
