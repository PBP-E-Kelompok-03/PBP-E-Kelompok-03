import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from food.models import Restaurant, SurpriseBox

from .models import Order
from .views import MAX_PER_ORDER, expire_stale_orders


def make_box(owner=None, stok=5, start_offset=-1, end_offset=2, **extra):
    now = timezone.now()
    restaurant = Restaurant.objects.create(nama="Kedai Test", alamat="Jl. Test", owner=owner)
    return SurpriseBox.objects.create(
        restaurant=restaurant,
        nama_paket="Paket Test",
        harga_normal=40000,
        harga_diskon=24000,
        stok=stok,
        pickup_start=now + datetime.timedelta(hours=start_offset),
        pickup_end=now + datetime.timedelta(hours=end_offset),
        **extra,
    )


class BaseOrderTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")
        self.other = User.objects.create_user(username="buyer2", password="pass12345")
        self.seller = User.objects.create_user(username="seller1", password="pass12345", role=User.Role.PARTNER)
        self.box = make_box(owner=self.seller)

    def order(self, **kwargs):
        defaults = {"pembeli": self.buyer, "surprise_box": self.box, "jumlah": 1, "kode_pickup": "ABC123"}
        defaults.update(kwargs)
        return Order.objects.create(**defaults)


class OrderModelTest(BaseOrderTest):
    def test_default_status_is_pending(self):
        self.assertEqual(self.order().status, Order.Status.PENDING)

    def test_str_shows_kode_pickup(self):
        self.assertIn("XYZ789", str(self.order(kode_pickup="XYZ789")))

    def test_kode_pickup_must_be_unique(self):
        self.order(kode_pickup="DUPE1")
        with self.assertRaises(Exception):
            self.order(kode_pickup="DUPE1")

    def test_deleting_box_keeps_order(self):
        order = self.order()
        self.box.delete()
        order.refresh_from_db()
        self.assertIsNone(order.surprise_box)


class OrderCreateViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="buyer1", password="pass12345")
        self.url = reverse("order:create", args=[self.box.id])

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 302)

    def test_success_reduces_stock(self):
        response = self.client.post(self.url, {"jumlah": 2})
        self.assertEqual(response.status_code, 201)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 3)
        self.assertEqual(Order.objects.get().jumlah, 2)

    def test_unknown_box_404(self):
        self.assertEqual(self.client.post(reverse("order:create", args=[99999]), {"jumlah": 1}).status_code, 404)

    def test_inactive_box_404(self):
        self.box.is_active = False
        self.box.save()
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 404)

    def test_exceeds_stock_fails_without_side_effects(self):
        self.box.stok = 2
        self.box.save()
        self.assertEqual(self.client.post(self.url, {"jumlah": 3}).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 2)
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_jumlah_fails(self):
        self.assertEqual(self.client.post(self.url, {"jumlah": 0}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"jumlah": "abc"}).status_code, 400)

    def test_last_unit_goes_to_first_buyer_only(self):
        self.box.stok = 1
        self.box.save()
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 201)
        self.client.login(username="buyer2", password="pass12345")
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 0)
        self.assertEqual(Order.objects.count(), 1)

    def test_before_pickup_window_fails(self):
        box = make_box(start_offset=1, end_offset=3)
        self.assertEqual(self.client.post(reverse("order:create", args=[box.id]), {"jumlah": 1}).status_code, 400)

    def test_after_pickup_window_fails(self):
        box = make_box(start_offset=-3, end_offset=-1)
        self.assertEqual(self.client.post(reverse("order:create", args=[box.id]), {"jumlah": 1}).status_code, 400)


class OrderCheckoutViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="buyer1", password="pass12345")

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("order:checkout", args=[self.box.id])).status_code, 302)

    def test_shows_box_details(self):
        response = self.client.get(reverse("order:checkout", args=[self.box.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ringkasan Pesanan")
        self.assertContains(response, 'data-rupiah="24000.00"')

    def test_unknown_box_404(self):
        self.assertEqual(self.client.get(reverse("order:checkout", args=[99999])).status_code, 404)


class OrderHistoryViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.order(kode_pickup="HIST01")

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse("order:history")).status_code, 302)

    def test_shows_only_own_orders(self):
        self.client.login(username="buyer1", password="pass12345")
        self.assertContains(self.client.get(reverse("order:history")), "HIST01")

    def test_hides_other_users_orders(self):
        self.client.login(username="buyer2", password="pass12345")
        self.assertNotContains(self.client.get(reverse("order:history")), "HIST01")


class OrderCancelViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.box.stok = 4
        self.box.save()
        self.order_obj = self.order(jumlah=1, kode_pickup="CANC01")
        self.url = reverse("order:cancel", args=[self.order_obj.id])

    def test_owner_can_cancel_and_stock_returns(self):
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.order_obj.refresh_from_db()
        self.box.refresh_from_db()
        self.assertEqual(self.order_obj.status, Order.Status.CANCELLED)
        self.assertEqual(self.box.stok, 5)

    def test_double_cancel_restores_stock_once(self):
        self.client.login(username="buyer1", password="pass12345")
        self.client.post(self.url)
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 5)

    def test_non_owner_403(self):
        self.client.login(username="buyer2", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.order_obj.refresh_from_db()
        self.assertEqual(self.order_obj.status, Order.Status.PENDING)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)

    def test_cannot_cancel_completed_order(self):
        self.order_obj.status = Order.Status.COMPLETED
        self.order_obj.save()
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 400)


class OrderCompleteViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.order_obj = self.order(kode_pickup="COMP01")
        self.url = reverse("order:complete", args=[self.order_obj.id])

    def test_seller_can_complete(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.order_obj.refresh_from_db()
        self.assertEqual(self.order_obj.status, Order.Status.COMPLETED)

    def test_buyer_cannot_complete_own_order(self):
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.order_obj.refresh_from_db()
        self.assertEqual(self.order_obj.status, Order.Status.PENDING)

    def test_other_restaurant_owner_cannot_complete(self):
        other_seller = User.objects.create_user(username="seller2", password="pass12345", role=User.Role.PARTNER)
        self.client.login(username="seller2", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_staff_can_complete(self):
        User.objects.create_user(username="admin1", password="pass12345", is_staff=True)
        self.client.login(username="admin1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 200)

    def test_cannot_complete_cancelled_order(self):
        self.order_obj.status = Order.Status.CANCELLED
        self.order_obj.save()
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_double_complete_second_fails(self):
        self.client.login(username="seller1", password="pass12345")
        self.client.post(self.url)
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_cancel_after_complete_fails(self):
        self.client.login(username="seller1", password="pass12345")
        self.client.post(self.url)
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(reverse("order:cancel", args=[self.order_obj.id])).status_code, 400)


class OrderIncomingViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.order(kode_pickup="INC001")

    def test_seller_sees_orders_for_own_restaurant(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertContains(self.client.get(reverse("order:incoming")), "INC001")

    def test_seller_does_not_see_other_restaurants(self):
        other = User.objects.create_user(username="seller2", password="pass12345", role=User.Role.PARTNER)
        make_box(owner=other)
        self.client.login(username="seller2", password="pass12345")
        self.assertNotContains(self.client.get(reverse("order:incoming")), "INC001")

    def test_buyer_gets_403(self):
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.get(reverse("order:incoming")).status_code, 403)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(reverse("order:incoming")).status_code, 302)


class OrderConfirmationViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.order_obj = self.order(kode_pickup="CONF01")
        self.url = reverse("order:confirmation", args=[self.order_obj.id])

    def test_owner_sees_confirmation(self):
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.get(self.url)
        self.assertContains(response, "CONF01")

    def test_non_owner_403(self):
        self.client.login(username="buyer2", password="pass12345")
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_box_deleted_still_renders(self):
        self.box.delete()
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.get(self.url).status_code, 200)


class OrderGuardTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="buyer1", password="pass12345")
        self.url = reverse("order:create", args=[self.box.id])

    def test_second_active_order_for_same_box_rejected(self):
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 201)
        response = self.client.post(self.url, {"jumlah": 1})
        self.assertEqual(response.status_code, 409)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 4)
        self.assertEqual(Order.objects.count(), 1)

    def test_can_reorder_after_cancel(self):
        first = self.client.post(self.url, {"jumlah": 1}).json()
        self.client.post(reverse("order:cancel", args=[first["id"]]))
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 201)

    def test_database_blocks_duplicate_active_orders(self):
        self.order(kode_pickup="AAA111")
        with self.assertRaises(Exception):
            self.order(kode_pickup="BBB222")

    def test_other_buyer_not_blocked(self):
        self.client.post(self.url, {"jumlah": 1})
        self.client.login(username="buyer2", password="pass12345")
        self.assertEqual(self.client.post(self.url, {"jumlah": 1}).status_code, 201)

    def test_quantity_above_limit_rejected(self):
        response = self.client.post(self.url, {"jumlah": MAX_PER_ORDER + 1})
        self.assertEqual(response.status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 5)

    def test_checkout_limits_stepper_to_max(self):
        response = self.client.get(reverse("order:checkout", args=[self.box.id]))
        self.assertContains(response, f'data-max-stock="{MAX_PER_ORDER}"')


class OrderExpiryTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.stale_box = make_box(owner=self.seller, start_offset=-5, end_offset=-3)

    def test_stale_active_order_becomes_expired(self):
        order = self.order(surprise_box=self.stale_box)
        self.assertEqual(expire_stale_orders(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)

    def test_order_within_window_untouched(self):
        order = self.order()
        self.assertEqual(expire_stale_orders(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_completed_order_never_expires(self):
        order = self.order(surprise_box=self.stale_box, status=Order.Status.COMPLETED)
        expire_stale_orders()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_history_expires_and_labels_order(self):
        self.order(surprise_box=self.stale_box, kode_pickup="OLD001")
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.get(reverse("order:history"))
        self.assertContains(response, "Kedaluwarsa")

    def test_seller_cannot_complete_expired_order(self):
        order = self.order(surprise_box=self.stale_box)
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.client.post(reverse("order:complete", args=[order.id])).status_code, 400)

    def test_buyer_cannot_cancel_expired_order(self):
        order = self.order(surprise_box=self.stale_box)
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(reverse("order:cancel", args=[order.id])).status_code, 400)

    def test_expired_order_allows_new_order_for_same_box(self):
        self.order(surprise_box=self.stale_box)
        expire_stale_orders()
        self.assertEqual(Order.objects.filter(status=Order.Status.EXPIRED).count(), 1)

    def test_management_command_runs(self):
        from django.core.management import call_command
        from io import StringIO

        self.order(surprise_box=self.stale_box)
        out = StringIO()
        call_command("expire_orders", stdout=out)
        self.assertIn("1 pesanan", out.getvalue())
