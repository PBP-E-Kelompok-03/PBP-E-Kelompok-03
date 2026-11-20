from django.core.cache import cache
from django.test import TestCase

from accounts.models import User
from food.models import Restaurant, SurpriseBox

from .models import Order


class ApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")
        self.seller = User.objects.create_user(username="seller1", password="pass12345", role=User.Role.PARTNER)
        resto = Restaurant.objects.create(nama="Kedai", alamat="Jl. Test", owner=self.seller)
        self.box = SurpriseBox.objects.create(
            restaurant=resto, nama_paket="Paket", harga_normal=40000, harga_diskon=24000, stok=5
        )

    def post(self, url, data=None):
        return self.client.post(url, data or {}, content_type="application/json")

    def make_order(self):
        self.client.force_login(self.buyer)
        return self.post("/api/order/orders/", {"box_id": self.box.id, "jumlah": 2}).json()


class AuthApiTest(TestCase):
    def test_register_login_me_logout(self):
        res = self.client.post(
            "/api/auth/register/",
            {"username": "dyah", "password1": "kataSandi123!", "password2": "kataSandi123!", "role": "buyer"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        res = self.client.post("/api/auth/login/", {"username": "dyah", "password": "kataSandi123!"}, content_type="application/json")
        self.assertTrue(res.json()["status"])
        self.assertEqual(self.client.get("/api/auth/me/").json()["username"], "dyah")
        self.client.post("/api/auth/logout/")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_login_wrong_password(self):
        User.objects.create_user(username="dyah", password="benar12345")
        res = self.client.post("/api/auth/login/", {"username": "dyah", "password": "salah"}, content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_register_password_mismatch(self):
        res = self.client.post(
            "/api/auth/register/",
            {"username": "dyah", "password1": "kataSandi123!", "password2": "beda", "role": "buyer"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["status"])


class OrderApiTest(ApiTest):
    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/order/orders/").status_code, 403)

    def test_boxes_list(self):
        self.client.force_login(self.buyer)
        data = self.client.get("/api/order/boxes/").json()
        self.assertEqual(data[0]["nama_paket"], "Paket")

    def test_create_reduces_stock(self):
        data = self.make_order()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(float(data["total"]), 48000)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 3)

    def test_create_duplicate_active_order(self):
        self.make_order()
        res = self.post("/api/order/orders/", {"box_id": self.box.id, "jumlah": 1})
        self.assertEqual(res.status_code, 409)

    def test_create_over_max_or_stock(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.post("/api/order/orders/", {"box_id": self.box.id, "jumlah": 9}).status_code, 400)

    def test_partner_cannot_create(self):
        self.client.force_login(self.seller)
        self.assertEqual(self.post("/api/order/orders/", {"box_id": self.box.id}).status_code, 403)

    def test_list_scoped_by_role(self):
        self.make_order()
        other = User.objects.create_user(username="buyer2", password="pass12345")
        self.client.force_login(other)
        self.assertEqual(self.client.get("/api/order/orders/").json(), [])
        self.client.force_login(self.seller)
        self.assertEqual(len(self.client.get("/api/order/orders/").json()), 1)

    def test_cancel_restores_stock(self):
        order = self.make_order()
        res = self.post(f"/api/order/orders/{order['id']}/cancel/")
        self.assertEqual(res.json()["status"], "cancelled")
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 5)

    def test_seller_flow_confirm_then_complete(self):
        order = self.make_order()
        self.client.force_login(self.seller)
        url = f"/api/order/orders/{order['id']}"
        self.assertEqual(self.post(f"{url}/complete/", {"kode_pickup": order["kode_pickup"]}).status_code, 400)
        self.assertEqual(self.post(f"{url}/confirm/").json()["status"], "confirmed")
        self.assertEqual(self.post(f"{url}/complete/", {"kode_pickup": "SALAH"}).status_code, 400)
        res = self.post(f"{url}/complete/", {"kode_pickup": order["kode_pickup"].lower()})
        self.assertEqual(res.json()["status"], "completed")

    def test_buyer_cannot_confirm(self):
        order = self.make_order()
        res = self.post(f"/api/order/orders/{order['id']}/confirm/")
        self.assertEqual(res.status_code, 403)

    def test_seller_reject(self):
        order = self.make_order()
        self.client.force_login(self.seller)
        self.assertEqual(self.post(f"/api/order/orders/{order['id']}/reject/").json()["status"], "cancelled")
        self.assertEqual(Order.objects.get().status, "cancelled")
