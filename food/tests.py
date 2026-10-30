import datetime
import io
import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from food.api_client import FoodApiClient
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
        cache.clear()
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

    def tearDown(self):
        cache.clear()

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

    def test_restaurant_detail_caps_quantity_like_checkout(self):
        SurpriseBox.objects.filter(restaurant=self.restaurant).update(stok=9)
        response = self.client.get(reverse("food:restaurant_detail", args=[self.restaurant.id]))
        self.assertEqual(response.context["max_per_order"], 3)
        self.assertContains(response, "maks. 3/pesanan")
        self.assertContains(response, "Math.min(parseInt(card.dataset.stock, 10) || 1, 3)")

    def test_restaurant_detail_not_found(self):
        response = self.client.get(reverse("food:restaurant_detail", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_create_restaurant_requires_login(self):
        response = self.client.get(reverse("food:create_restaurant"))
        self.assertEqual(response.status_code, 302)

    def test_buyer_cannot_create_restaurant(self):
        self.client.login(username="buyer1", password="password123")
        response = self.client.get(reverse("food:create_restaurant"))
        self.assertEqual(response.status_code, 403)

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


class FoodApiClientTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client_wrapper = FoodApiClient(timeout=2.0, cache_ttl=60)
        self.partner = User.objects.create_user(
            username="mitra_api", password="password123", role="partner"
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.partner,
            nama="Cafe API Test",
            alamat="Jl. Sudirman No. 10",
            lat=-6.21,
            lng=106.82,
            jam_buka=datetime.time(7, 30),
            jam_tutup=datetime.time(22, 0),
        )
        self.box = SurpriseBox.objects.create(
            restaurant=self.restaurant,
            nama_paket="Surprise Box Kopi",
            harga_normal=50000,
            harga_diskon=25000,
            stok=10,
        )

    def tearDown(self):
        cache.clear()

    # --- Skenario API Berhasil ---
    def test_get_restaurants_success_and_cache(self):
        """Memastikan data restoran diambil dari model database dan disimpan dalam cache."""
        res1 = self.client_wrapper.get_restaurants()
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["nama"], "Cafe API Test")
        self.assertEqual(res1[0]["lat"], -6.21)

        # Cek apakah tersimpan di cache
        cached_data = cache.get("food:restaurants:q_all")
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data[0]["nama"], "Cafe API Test")

        # Pemanggilan kedua membaca cache
        res2 = self.client_wrapper.get_restaurants()
        self.assertEqual(res2, cached_data)

    def test_get_surprise_boxes_filtered(self):
        """Memastikan filter query dan restaurant_id berfungsi pada API client."""
        boxes = self.client_wrapper.get_surprise_boxes(
            restaurant_id=self.restaurant.id, query="Kopi"
        )
        self.assertEqual(len(boxes), 1)
        self.assertEqual(boxes[0]["nama_paket"], "Surprise Box Kopi")

        # Query tidak cocok mengembalikan list kosong
        empty_boxes = self.client_wrapper.get_surprise_boxes(query="NonExistentItem")
        self.assertEqual(empty_boxes, [])

    def test_get_restaurant_detail_success(self):
        """Memastikan detail satu restoran dikembalikan dengan benar."""
        detail = self.client_wrapper.get_restaurant_detail(self.restaurant.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["nama"], "Cafe API Test")

        # Restoran tidak ada mengembalikan None
        not_found = self.client_wrapper.get_restaurant_detail(999999)
        self.assertIsNone(not_found)

    @patch("urllib.request.urlopen")
    def test_fetch_url_success_and_cache(self, mock_urlopen):
        """Skenario sukses HTTP request: parsing JSON 200 OK dan caching."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({"status": "ok", "items": [1, 2]}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        url = "https://api.dibuangsayang.local/v1/test"
        result = self.client_wrapper.fetch_url(url, timeout=3.0)

        self.assertFalse(result["fallback"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["data"]["status"], "ok")
        self.assertIsNone(result["error"])

        # Panggilan kedua harus membaca dari cache
        cached_result = self.client_wrapper.fetch_url(url)
        self.assertTrue(cached_result["from_cache"])
        self.assertEqual(cached_result["data"]["status"], "ok")

    # --- Skenario API Gagal & Fallback ---
    @patch("urllib.request.urlopen")
    def test_fetch_url_timeout_triggers_fallback(self, mock_urlopen):
        """Skenario gagal Timeout: memicu fallback aman tanpa error 500."""
        mock_urlopen.side_effect = socket.timeout("Request timed out")

        url = "https://api.dibuangsayang.local/v1/slow"
        result = self.client_wrapper.fetch_url(url, timeout=1.0)

        self.assertTrue(result["fallback"])
        self.assertEqual(result["status_code"], 504)
        self.assertEqual(result["error"], "timeout")
        self.assertEqual(result["data"], {})

    @patch("urllib.request.urlopen")
    def test_fetch_url_http_error_triggers_fallback(self, mock_urlopen):
        """Skenario gagal HTTP 500: menangani error dan mengembalikan fallback."""
        err = urllib.error.HTTPError(
            url="https://api.dibuangsayang.local/v1/error",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"server error"),
        )
        mock_urlopen.side_effect = err

        url = "https://api.dibuangsayang.local/v1/error"
        result = self.client_wrapper.fetch_url(url)

        self.assertTrue(result["fallback"])
        self.assertEqual(result["status_code"], 500)
        self.assertIn("Internal Server Error", result["error"])

    @patch("urllib.request.urlopen")
    def test_fetch_url_network_error_triggers_fallback(self, mock_urlopen):
        """Skenario gagal koneksi jaringan: mengembalikan fallback aman."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        url = "https://api.dibuangsayang.local/v1/down"
        result = self.client_wrapper.fetch_url(url)

        self.assertTrue(result["fallback"])
        self.assertEqual(result["status_code"], 503)
        self.assertEqual(result["error"], "Connection refused")

    @patch("food.api_client.Restaurant.objects.filter")
    def test_get_restaurants_db_error_triggers_fallback(self, mock_filter):
        """Skenario gagal query database: menangkap exception dan mengembalikan fallback list kosong."""
        mock_filter.side_effect = Exception("Database connection failure")

        result = self.client_wrapper.get_restaurants(use_cache=False)
        self.assertEqual(result, [])


class FoodDatabaseExclusivityTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_empty_database_shows_empty_state_without_json_fallback(self):
        """
        Memastikan jika database kosong dari SurpriseBox/Restaurant,
        halaman food_list menampilkan empty state murni dari database,
        TIDAK membaca file dummy_data.json.
        """
        self.assertEqual(Restaurant.objects.count(), 0)
        self.assertEqual(SurpriseBox.objects.count(), 0)

        response = self.client.get(reverse("food:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["surprise_boxes"]), 0)
        self.assertEqual(response.context["total_restaurants"], 0)
        self.assertContains(response, "Tidak ada paket Surprise Box yang ditemukan")

    def test_empty_database_api_returns_empty_list(self):
        """
        Memastikan endpoint API JSON mengembalikan list kosong jika database kosong,
        bukan data dari file JSON.
        """
        res_rest = self.client.get(reverse("food:api_restaurants"))
        self.assertEqual(res_rest.status_code, 200)
        self.assertEqual(res_rest.json(), {"restaurants": []})

        res_box = self.client.get(reverse("food:api_surprise_boxes"))
        self.assertEqual(res_box.status_code, 200)
        self.assertEqual(res_box.json(), {"surprise_boxes": []})


class SeedFoodCommandTest(TestCase):
    def test_seed_assigns_demo_owner_and_if_empty_skips(self):
        from django.core.management import call_command

        call_command("seed_food", stdout=io.StringIO())
        owner = User.objects.get(username="mitra_demo")
        self.assertFalse(owner.has_usable_password())
        self.assertTrue(Restaurant.objects.exists())
        self.assertFalse(Restaurant.objects.exclude(owner=owner).exists())

        Restaurant.objects.filter(pk=Restaurant.objects.first().pk).update(nama="Diubah")
        call_command("seed_food", "--if-empty", stdout=io.StringIO())
        self.assertTrue(Restaurant.objects.filter(nama="Diubah").exists())
