import datetime
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import resolve, reverse
from django.utils import timezone, translation

from accounts.models import User
from food.models import Restaurant, SurpriseBox
from .models import RestaurantMapProfile
from .services import restaurant_locations
from .views import map_view


class MapViewTests(TestCase):
    def restaurant(self, **kwargs):
        return Restaurant.objects.create(
            **{"nama": "Warung Map", "alamat": "Jl. Margonda", "lat": -6.36, "lng": 106.83, **kwargs}
        )

    def box(self, restaurant, **kwargs):
        return SurpriseBox.objects.create(
            restaurant=restaurant,
            **{"nama_paket": "Paket", "harga_normal": 40000, "harga_diskon": 20000, "stok": 3, **kwargs}
        )

    def data(self):
        response = self.client.get(reverse("map:restaurants_data"))
        self.assertEqual(response.status_code, 200)
        return response.json()["restaurants"]

    def test_route_resolves_to_map_view(self):
        self.assertEqual(reverse("map:map"), "/map/")
        self.assertEqual(resolve("/map/").func, map_view)

    def test_public_map_contains_restaurant_details_and_radius_options(self):
        restaurant = self.restaurant(jam_buka=datetime.time(8), jam_tutup=datetime.time(21))
        response = self.client.get("/map/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "map/map.html")
        for value in (restaurant.nama, restaurant.alamat, "08:00",
                      reverse("food:restaurant_detail", args=[restaurant.pk])):
            self.assertContains(response, value)
        for radius in (1, 3, 5):
            self.assertContains(response, f'<option value="{radius}">{radius} km</option>')
        self.assertEqual(response.context["restaurants"][0]["lat"], -6.36)

    def test_directions_use_database_coordinates_without_localized_decimals(self):
        expected = {}
        for lat, lng in [
            ("-6.365123", "106.833456"), ("0.000000", "0.000000"),
            ("0.000001", "-0.000001"), ("90.000000", "-180.000000"),
        ]:
            restaurant = self.restaurant(lat=Decimal(lat), lng=Decimal(lng))
            expected[restaurant.pk] = f"{lat},{lng}"
        with translation.override("id"):
            rows = self.data()
        self.assertEqual(len(rows), len(expected))
        for row in rows:
            url = urlsplit(row["directions_url"])
            self.assertEqual((url.scheme, url.netloc, url.path),
                             ("https", "www.google.com", "/maps/dir/"))
            self.assertEqual(parse_qs(url.query), {
                "api": ["1"], "destination": [expected[row["id"]]],
                "dir_action": ["navigate"],
            })

    def test_server_rendered_directions_are_usable_without_javascript(self):
        restaurants = [self.restaurant(nama="Warung & Kafe"), self.restaurant(lat=0, lng=0)]
        response = self.client.get(reverse("map:map"))
        links = []

        class DirectionsParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a" and "restaurant-directions-link" in attrs.get("class", "").split():
                    links.append(attrs)

        DirectionsParser().feed(response.content.decode())
        rows = {row["id"]: row for row in response.context["restaurants"]}
        self.assertEqual(len(links), len(restaurants))
        self.assertEqual({link["href"] for link in links},
                         {row["directions_url"] for row in rows.values()})
        for link in links:
            self.assertEqual(link["target"], "_blank")
            self.assertTrue({"noopener", "noreferrer"} <= set(link["rel"].split()))
        self.assertContains(response, "Arahkan ke Lokasi Warung &amp; Kafe di Google Maps")

    def test_directions_follow_coordinate_changes_even_when_stock_runs_out(self):
        restaurant = self.restaurant()
        box = self.box(restaurant, stok=1)
        previous = self.data()[0]["directions_url"]
        restaurant.lat, restaurant.lng = Decimal("-6.400123"), Decimal("106.900456")
        restaurant.save(update_fields=["lat", "lng"])
        box.stok = 0
        box.save(update_fields=["stok"])
        row = self.data()[0]
        self.assertEqual(row["stock_status"], "sold_out")
        self.assertNotEqual(row["directions_url"], previous)
        self.assertEqual(parse_qs(urlsplit(row["directions_url"]).query)["destination"],
                         ["-6.400123,106.900456"])

    def test_only_active_restaurants_with_valid_coordinates_are_mapped(self):
        valid = self.restaurant(nama="Valid", lat=0, lng=0)
        self.restaurant(nama="Inactive", is_active=False)
        self.restaurant(nama="Missing", lat=None)
        self.restaurant(nama="Out of bounds", lat=91, lng=181)
        self.assertEqual([r["id"] for r in self.data()], [valid.pk])

    def test_empty_or_inactive_database_never_uses_dummy_restaurants(self):
        self.assertEqual(self.data(), [])
        self.restaurant(is_active=False)
        response = self.client.get("/map/")
        self.assertEqual(response.context["restaurants"], [])
        self.assertContains(response, "Belum ada restoran dengan koordinat yang valid.")
        self.assertContains(response, 'id="restaurant-map"')

    def test_existing_rows_with_missing_coordinates_are_not_mapped(self):
        self.restaurant(lat=None, lng=None)
        self.assertEqual(self.data(), [])

    def test_restaurant_content_is_escaped_in_html_and_json(self):
        self.restaurant(nama='</script><script>alert("x")</script>', alamat="<img src=x>")
        response = self.client.get("/map/")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, r"\u003C/script\u003E")
        self.assertContains(response, "&lt;img src=x&gt;")

    def test_stock_and_lowest_price_only_include_available_active_boxes(self):
        restaurant = self.restaurant()
        self.box(restaurant, harga_diskon=22000, stok=2)
        self.box(restaurant, harga_diskon=12000, stok=4)
        self.box(restaurant, harga_diskon=1000, stok=0)
        self.box(restaurant, harga_diskon=500, stok=99, is_active=False)
        row = self.data()[0]
        self.assertEqual(row["total_stock"], 6)
        self.assertEqual(row["available_stock"], 6)
        self.assertTrue(row["has_stock"])
        self.assertTrue(row["is_available"])
        self.assertEqual(row["stock_status"], "available")
        self.assertEqual(Decimal(row["min_discount_price"]), Decimal("12000"))
        response = self.client.get("/map/")
        self.assertContains(response, "6 paket tersedia")
        self.assertContains(response, "Mulai Rp 12.000")

    def test_zero_price_is_valid_and_not_replaced_by_dummy_price(self):
        self.box(self.restaurant(), harga_diskon=0)
        self.assertEqual(Decimal(self.data()[0]["min_discount_price"]), 0)
        self.assertContains(self.client.get("/map/"), "Mulai Rp 0")

    def test_sold_out_and_no_boxes_have_no_available_price(self):
        self.restaurant(nama="No boxes")
        self.box(self.restaurant(nama="Sold out"), stok=0)
        for row in self.data():
            self.assertEqual(row["stock_status"], "sold_out")
            self.assertFalse(row["has_stock"])
            self.assertFalse(row["is_available"])
            self.assertEqual(row["available_stock"], 0)
            self.assertIsNone(row["min_discount_price"])

    def test_stock_and_price_update_when_cheapest_box_sells_out(self):
        restaurant = self.restaurant()
        cheapest = self.box(restaurant, harga_diskon=10000, stok=1)
        other = self.box(restaurant, harga_diskon=25000, stok=2)
        self.assertEqual(Decimal(self.data()[0]["min_discount_price"]), 10000)
        cheapest.stok = 0
        cheapest.save(update_fields=["stok"])
        row = self.data()[0]
        self.assertEqual(row["available_stock"], 2)
        self.assertEqual(Decimal(row["min_discount_price"]), 25000)
        other.is_active = False
        other.save(update_fields=["is_active"])
        self.assertEqual(self.data()[0]["stock_status"], "sold_out")

    def test_order_and_cancellation_change_map_stock(self):
        box = self.box(self.restaurant(), stok=1)
        buyer = User.objects.create_user(username="buyer", password="pass")
        self.client.force_login(buyer)
        response = self.client.post(reverse("order:create", args=[box.pk]), {"jumlah": 1})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.data()[0]["stock_status"], "sold_out")
        self.assertEqual(self.client.post(
            reverse("order:cancel", args=[response.json()["id"]])
        ).status_code, 200)
        self.assertEqual(self.data()[0]["available_stock"], 1)

    def test_photo_and_detail_url_come_from_matching_restaurant(self):
        restaurant = self.restaurant()
        RestaurantMapProfile.objects.create(restaurant=restaurant, image_url="https://example.com/restaurant.jpg")
        row = self.data()[0]
        self.assertEqual(row["image_url"], "https://example.com/restaurant.jpg")
        self.assertTrue(row["has_image"])
        detail = self.client.get(row["detail_url"])
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, restaurant.nama)

    def test_missing_or_invalid_photo_uses_local_placeholder(self):
        restaurant = self.restaurant()
        self.assertFalse(self.data()[0]["has_image"])
        RestaurantMapProfile.objects.create(restaurant=restaurant, image_url="javascript:alert(1)")
        row = self.data()[0]
        self.assertFalse(row["has_image"])
        self.assertTrue(row["image_url"].endswith("/map/restaurant-placeholder.svg"))

    def test_photo_and_boxes_are_loaded_without_per_restaurant_queries(self):
        for number in range(5):
            restaurant = self.restaurant(nama=f"Restaurant {number}")
            self.box(restaurant)
            RestaurantMapProfile.objects.create(restaurant=restaurant, image_url="https://example.com/photo.jpg")
        with self.assertNumQueries(1):
            self.assertEqual(len(restaurant_locations()), 5)

    def test_json_api_matches_page_and_disables_caching(self):
        self.box(self.restaurant())
        page = self.client.get("/map/")
        api = self.client.get(reverse("map:restaurants_data"))
        self.assertEqual(page.context["restaurants"], api.json()["restaurants"])
        for response in (page, api):
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.post(reverse("map:restaurants_data")).status_code, 405)

    def test_detail_cta_has_valid_decimal_javascript_and_truthful_zero_stock(self):
        restaurant = self.restaurant()
        self.box(restaurant, stok=0, harga_diskon=Decimal("12345.67"))
        response = self.client.get(reverse("food:restaurant_detail", args=[restaurant.pk]))
        self.assertContains(response, ", 12345.67, ")
        self.assertNotContains(response, "12345,67")
        self.assertContains(response, "0 paket tersisa")
        self.assertNotContains(response, "4 paket tersisa")


class RestaurantPhotoTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass", role="partner")
        self.other = User.objects.create_user(username="other", password="pass", role="partner")
        self.restaurant = Restaurant.objects.create(
            owner=self.owner, nama="Owner Restaurant", alamat="A", lat=0, lng=0,
        )
        self.url = reverse("map:restaurant_photo", args=[self.restaurant.pk])

    def test_photo_editor_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url, {"image_url": ""}).status_code, 302)

    def test_only_owner_or_staff_can_edit_photo(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"image_url": "https://example.com/other.jpg"}).status_code, 403)
        self.assertFalse(RestaurantMapProfile.objects.exists())
        self.other.is_staff = True
        self.other.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_owner_can_add_change_and_remove_photo(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(RestaurantMapProfile.objects.exists())
        for image_url in ("https://example.com/first.jpg", "https://example.com/second.jpg", ""):
            self.assertRedirects(self.client.post(self.url, {"image_url": image_url}), reverse("map:map"))
            self.assertEqual(RestaurantMapProfile.objects.get(restaurant=self.restaurant).image_url, image_url)
            row = self.client.get(reverse("map:restaurants_data")).json()["restaurants"][0]
            self.assertEqual(row["has_image"], bool(image_url))
            if image_url:
                self.assertEqual(row["image_url"], image_url)
        self.assertEqual(RestaurantMapProfile.objects.count(), 1)

    def test_rejects_unsafe_or_non_https_photo_urls(self):
        self.client.force_login(self.owner)
        for image_url in ("javascript:alert(1)", "http://example.com/photo.jpg", "not-a-url"):
            response = self.client.post(self.url, {"image_url": image_url})
            self.assertEqual(response.status_code, 200)
            self.assertIn("image_url", response.context["form"].errors)
        self.assertFalse(RestaurantMapProfile.objects.exists())

    def test_editor_link_is_only_shown_to_owner_or_staff(self):
        api_url = reverse("map:restaurants_data")
        self.assertIsNone(self.client.get(api_url).json()["restaurants"][0]["photo_edit_url"])
        self.client.force_login(self.other)
        self.assertIsNone(self.client.get(api_url).json()["restaurants"][0]["photo_edit_url"])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(api_url).json()["restaurants"][0]["photo_edit_url"], self.url)

    def test_photo_submission_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {"image_url": ""}).status_code, 403)

    def test_inactive_or_unknown_restaurant_cannot_be_edited(self):
        self.client.force_login(self.owner)
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(reverse("map:restaurant_photo", args=[99999])).status_code, 404)


class MapSecurityHeaderTests(TestCase):
    def test_http_and_https_map_allow_cross_origin_referrer(self):
        for secure in (False, True):
            with self.subTest(secure=secure):
                response = self.client.get(reverse("map:map"), secure=secure)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.headers["Referrer-Policy"], "strict-origin-when-cross-origin",
                )
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_https_proxy_keeps_referrer_policy_and_ssl_redirect(self):
        with self.settings(
            SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
            SECURE_SSL_REDIRECT=True,
        ):
            response = self.client.get(reverse("map:map"), HTTP_X_FORWARDED_PROTO="https")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers["Referrer-Policy"], "strict-origin-when-cross-origin",
            )
            self.assertEqual(self.client.get(reverse("map:map")).status_code, 301)
