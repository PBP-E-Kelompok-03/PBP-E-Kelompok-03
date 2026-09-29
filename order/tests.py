from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Order


class OrderModelTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")

    def test_order_default_status_is_pending(self):
        order = Order.objects.create(pembeli=self.buyer, surprise_box_id=1, jumlah=1, kode_pickup="ABC123")
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_order_str_shows_kode_pickup(self):
        order = Order.objects.create(pembeli=self.buyer, surprise_box_id=1, jumlah=2, kode_pickup="XYZ789")
        self.assertIn("XYZ789", str(order))

    def test_kode_pickup_must_be_unique(self):
        Order.objects.create(pembeli=self.buyer, surprise_box_id=1, jumlah=1, kode_pickup="DUPE1")
        with self.assertRaises(Exception):
            Order.objects.create(pembeli=self.buyer, surprise_box_id=1, jumlah=1, kode_pickup="DUPE1")


class OrderCreateViewTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")
        self.client.login(username="buyer1", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse("order:create", args=[1]), {"jumlah": 1})
        self.assertEqual(response.status_code, 302)

    def test_create_order_success(self):
        response = self.client.post(reverse("order:create", args=[1]), {"jumlah": 1})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.filter(pembeli=self.buyer, surprise_box_id=1).count(), 1)

    def test_create_order_unknown_box_fails(self):
        response = self.client.post(reverse("order:create", args=[99999]), {"jumlah": 1})
        self.assertEqual(response.status_code, 404)

    def test_create_order_exceeds_stock_fails(self):
        response = self.client.post(reverse("order:create", args=[1]), {"jumlah": 999})
        self.assertEqual(response.status_code, 400)

    def test_create_order_invalid_jumlah_fails(self):
        response = self.client.post(reverse("order:create", args=[1]), {"jumlah": 0})
        self.assertEqual(response.status_code, 400)

    def test_cancelled_orders_free_up_stock(self):
        response = self.client.post(reverse("order:create", args=[1]), {"jumlah": 1})
        order = Order.objects.get(pembeli=self.buyer, surprise_box_id=1)
        order.status = Order.Status.CANCELLED
        order.save()
        response2 = self.client.post(reverse("order:create", args=[1]), {"jumlah": 1})
        self.assertEqual(response2.status_code, 201)


class OrderHistoryViewTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")
        self.other = User.objects.create_user(username="buyer2", password="pass12345")
        self.order = Order.objects.create(pembeli=self.buyer, surprise_box_id=1, jumlah=1, kode_pickup="HIST01")

    def test_requires_login(self):
        response = self.client.get(reverse("order:history"))
        self.assertEqual(response.status_code, 302)

    def test_shows_only_own_orders(self):
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.get(reverse("order:history"))
        self.assertContains(response, "HIST01")

    def test_does_not_show_other_users_orders(self):
        self.client.login(username="buyer2", password="pass12345")
        response = self.client.get(reverse("order:history"))
        self.assertNotContains(response, "HIST01")


class OrderCancelViewTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")
        self.other = User.objects.create_user(username="buyer2", password="pass12345")
        self.order = Order.objects.create(pembeli=self.buyer, surprise_box_id=1, jumlah=1, kode_pickup="CANC01")

    def test_owner_can_cancel(self):
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.post(reverse("order:cancel", args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_non_owner_gets_403(self):
        self.client.login(username="buyer2", password="pass12345")
        response = self.client.post(reverse("order:cancel", args=[self.order.id]))
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_anonymous_redirected(self):
        response = self.client.post(reverse("order:cancel", args=[self.order.id]))
        self.assertEqual(response.status_code, 302)
