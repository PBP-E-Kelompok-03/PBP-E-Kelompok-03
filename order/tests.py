import datetime
import threading

from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from django.db.backends.signals import connection_created
from django.test import Client

from accounts.models import User
from food.models import Restaurant, SurpriseBox

from .models import Order
from .views import MAX_PER_ORDER, expire_stale_orders



def make_box(owner=None, stok=5, **extra):
    restaurant = Restaurant.objects.create(nama="Kedai Test", alamat="Jl. Test", owner=owner)
    return SurpriseBox.objects.create(
        restaurant=restaurant,
        nama_paket="Paket Test",
        harga_normal=40000,
        harga_diskon=24000,
        stok=stok,
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

    def test_cannot_cancel_confirmed_order(self):
        self.order_obj.status = Order.Status.CONFIRMED
        self.order_obj.save()
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.order_obj.refresh_from_db()
        self.box.refresh_from_db()
        self.assertEqual(self.order_obj.status, Order.Status.CONFIRMED)
        self.assertEqual(self.box.stok, 4)


class OrderCompleteViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.order_obj = self.order(kode_pickup="COMP01", status=Order.Status.CONFIRMED)
        self.url = reverse("order:complete", args=[self.order_obj.id])

    def complete(self, code="COMP01"):
        return self.client.post(self.url, {"kode_pickup": code})

    def status(self):
        self.order_obj.refresh_from_db()
        return self.order_obj.status

    def test_seller_can_complete(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.complete().status_code, 200)
        self.assertEqual(self.status(), Order.Status.COMPLETED)

    def test_code_ignores_case_and_spaces(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.complete(" comp01 ").status_code, 200)

    def test_wrong_code_rejected(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.complete("WRONG1").status_code, 400)
        self.assertEqual(self.status(), Order.Status.CONFIRMED)

    def test_missing_code_rejected(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.assertEqual(self.status(), Order.Status.CONFIRMED)

    def test_cannot_complete_pending_order(self):
        self.order_obj.status = Order.Status.PENDING
        self.order_obj.save()
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.complete().status_code, 400)
        self.assertEqual(self.status(), Order.Status.PENDING)

    def test_buyer_cannot_complete_own_order(self):
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.complete().status_code, 403)
        self.assertEqual(self.status(), Order.Status.CONFIRMED)

    def test_other_restaurant_owner_cannot_complete(self):
        User.objects.create_user(username="seller2", password="pass12345", role=User.Role.PARTNER)
        self.client.login(username="seller2", password="pass12345")
        self.assertEqual(self.complete().status_code, 403)

    def test_staff_can_complete_with_code(self):
        User.objects.create_user(username="admin1", password="pass12345", is_staff=True)
        self.client.login(username="admin1", password="pass12345")
        self.assertEqual(self.complete().status_code, 200)

    def test_cannot_complete_cancelled_order(self):
        self.order_obj.status = Order.Status.CANCELLED
        self.order_obj.save()
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.complete().status_code, 400)

    def test_double_complete_second_fails(self):
        self.client.login(username="seller1", password="pass12345")
        self.complete()
        self.assertEqual(self.complete().status_code, 400)

    def test_cancel_after_complete_fails(self):
        self.client.login(username="seller1", password="pass12345")
        self.complete()
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(reverse("order:cancel", args=[self.order_obj.id])).status_code, 400)


class OrderConfirmViewTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.order_obj = self.order(kode_pickup="CNF001")
        self.url = reverse("order:confirm", args=[self.order_obj.id])

    def status(self):
        self.order_obj.refresh_from_db()
        return self.order_obj.status

    def test_seller_can_confirm(self):
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.assertEqual(self.status(), Order.Status.CONFIRMED)

    def test_staff_can_confirm(self):
        User.objects.create_user(username="admin1", password="pass12345", is_staff=True)
        self.client.login(username="admin1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 200)

    def test_buyer_cannot_confirm(self):
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(self.status(), Order.Status.PENDING)

    def test_other_restaurant_owner_cannot_confirm(self):
        User.objects.create_user(username="seller2", password="pass12345", role=User.Role.PARTNER)
        self.client.login(username="seller2", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)

    def test_double_confirm_fails(self):
        self.client.login(username="seller1", password="pass12345")
        self.client.post(self.url)
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_cannot_confirm_cancelled_order(self):
        self.order_obj.status = Order.Status.CANCELLED
        self.order_obj.save()
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(self.client.post(self.url).status_code, 400)

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


class PartnerRestrictionTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.partner = User.objects.create_user(username="newpartner", password="pass12345", role=User.Role.PARTNER)
        self.client.login(username="newpartner", password="pass12345")

    def test_partner_cannot_create_order(self):
        response = self.client.post(reverse("order:create", args=[self.box.id]), {"jumlah": 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Order.objects.count(), 0)

    def test_partner_cannot_open_checkout(self):
        self.assertEqual(self.client.get(reverse("order:checkout", args=[self.box.id])).status_code, 403)

    def test_partner_without_restaurant_sees_empty_incoming(self):
        self.assertEqual(self.client.get(reverse("order:incoming")).status_code, 200)


class OrderRejectTest(BaseOrderTest):
    def setUp(self):
        super().setUp()
        self.client.login(username="seller1", password="pass12345")

    def url(self, order):
        return reverse("order:reject", args=[order.id])

    def test_seller_rejects_pending_and_stock_returns(self):
        order = self.order()
        response = self.client.post(self.url(order))
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.box.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.box.stok, 6)

    def test_seller_rejects_confirmed(self):
        order = self.order(status=Order.Status.CONFIRMED)
        self.assertEqual(self.client.post(self.url(order)).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_completed_cannot_be_rejected(self):
        order = self.order(status=Order.Status.COMPLETED)
        self.assertEqual(self.client.post(self.url(order)).status_code, 400)

    def test_reject_twice_returns_stock_once(self):
        order = self.order()
        self.client.post(self.url(order))
        self.assertEqual(self.client.post(self.url(order)).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 6)

    def test_buyer_cannot_reject(self):
        order = self.order()
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(self.url(order)).status_code, 403)

    def test_other_seller_cannot_reject(self):
        order = self.order()
        User.objects.create_user(username="seller2", password="pass12345", role=User.Role.PARTNER)
        self.client.login(username="seller2", password="pass12345")
        self.assertEqual(self.client.post(self.url(order)).status_code, 403)

    def test_get_not_allowed(self):
        order = self.order()
        self.assertEqual(self.client.get(self.url(order)).status_code, 405)


class OrderPriceSnapshotTest(BaseOrderTest):
    def test_order_keeps_price_when_box_price_changes(self):
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.post(reverse("order:create", args=[self.box.id]), {"jumlah": 2})
        order = Order.objects.get(pk=response.json()["id"])
        self.assertEqual(order.harga_satuan, 24000)
        SurpriseBox.objects.filter(pk=self.box.pk).update(harga_diskon=1000)
        page = self.client.get(reverse("order:confirmation", args=[order.id]))
        self.assertContains(page, 'data-unit="24000.00"')

    def test_total_survives_deleted_box(self):
        self.client.login(username="buyer1", password="pass12345")
        order = self.order(harga_satuan=24000)
        self.box.delete()
        self.assertContains(self.client.get(reverse("order:confirmation", args=[order.id])), 'data-unit="24000.00"')


class OrderStaleStockTest(BaseOrderTest):
    def test_other_buyers_stale_order_releases_stock_on_create(self):
        SurpriseBox.objects.filter(pk=self.box.pk).update(stok=0)
        stale = self.order(pembeli=self.other, kode_pickup="OLD999")
        Order.objects.filter(pk=stale.pk).update(dibuat_pada=timezone.now() - datetime.timedelta(hours=25))
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.post(reverse("order:create", args=[self.box.id]), {"jumlah": 1})
        self.assertEqual(response.status_code, 201)


class OrderHistoryRestaurantTest(BaseOrderTest):
    def test_history_shows_restaurant_name(self):
        self.order()
        self.client.login(username="buyer1", password="pass12345")
        self.assertContains(self.client.get(reverse("order:history")), "Kedai Test")


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
    def stale_order(self, **kwargs):
        order = self.order(**kwargs)
        Order.objects.filter(pk=order.pk).update(dibuat_pada=timezone.now() - datetime.timedelta(hours=25))
        order.refresh_from_db()
        return order

    def test_stale_active_order_becomes_expired_and_restores_stock(self):
        order = self.stale_order()
        self.assertEqual(expire_stale_orders(), 1)
        order.refresh_from_db()
        self.box.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertEqual(self.box.stok, 6)

    def test_fresh_order_untouched(self):
        order = self.order()
        self.assertEqual(expire_stale_orders(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_completed_order_never_expires(self):
        order = self.stale_order(status=Order.Status.COMPLETED)
        expire_stale_orders()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_history_expires_and_labels_order(self):
        self.stale_order(kode_pickup="OLD001")
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.get(reverse("order:history"))
        self.assertContains(response, "Kedaluwarsa")

    def test_seller_cannot_complete_expired_order(self):
        order = self.stale_order()
        self.client.login(username="seller1", password="pass12345")
        self.assertEqual(
            self.client.post(reverse("order:complete", args=[order.id]), {"kode_pickup": "ABC123"}).status_code, 400
        )

    def test_buyer_cannot_cancel_expired_order(self):
        order = self.stale_order()
        self.client.login(username="buyer1", password="pass12345")
        self.assertEqual(self.client.post(reverse("order:cancel", args=[order.id])).status_code, 400)

    def test_expired_order_allows_new_order_for_same_box(self):
        self.stale_order()
        self.client.login(username="buyer1", password="pass12345")
        response = self.client.post(reverse("order:create", args=[self.box.id]), {"jumlah": 1})
        self.assertEqual(response.status_code, 201)

    def test_management_command_runs(self):
        from django.core.management import call_command
        from io import StringIO

        self.stale_order()
        out = StringIO()
        call_command("expire_orders", stdout=out)
        self.assertIn("1 pesanan", out.getvalue())


def _set_sqlite_busy_timeout(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.cursor().execute("PRAGMA busy_timeout = 20000")


class OrderStockRaceConditionTest(TransactionTestCase):
    def setUp(self):
        connection_created.connect(_set_sqlite_busy_timeout)
        self.addCleanup(connection_created.disconnect, _set_sqlite_busy_timeout)

        self.seller = User.objects.create_user(username="seller1", password="pass12345", role=User.Role.PARTNER)
        self.box = make_box(owner=self.seller, stok=1)
        self.url = reverse("order:create", args=[self.box.id])
        self.clients = []
        for name in ("buyer1", "buyer2"):
            User.objects.create_user(username=name, password="pass12345")
            client = Client()
            client.login(username=name, password="pass12345")
            self.clients.append(client)

    def test_last_unit_only_one_request_succeeds(self):
        barrier = threading.Barrier(2)
        statuses = []
        errors = []

        def attempt(client):
            try:
                barrier.wait(timeout=5)
                statuses.append(client.post(self.url, {"jumlah": 1}).status_code)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=attempt, args=(c,)) for c in self.clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(sorted(statuses), [201, 400])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(SurpriseBox.objects.get(pk=self.box.pk).stok, 0)
