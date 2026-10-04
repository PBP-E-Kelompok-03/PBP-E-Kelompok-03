import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import resolve, reverse

from food.models import Restaurant
from .views import map_view


class MapViewTests(TestCase):
    def test_route_resolves_to_map_view(self):
        self.assertEqual(reverse("map:map"), "/map/")
        self.assertEqual(resolve("/map/").func, map_view)

    def test_public_map_contains_restaurant_details_and_radius_options(self):
        restaurant = Restaurant.objects.create(
            nama="Warung Map", alamat="Jl. Margonda", lat=-6.36, lng=106.83,
            jam_buka=datetime.time(8), jam_tutup=datetime.time(21),
        )
        response = self.client.get("/map/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "map/map.html")
        self.assertContains(response, restaurant.nama)
        self.assertContains(response, restaurant.alamat)
        self.assertContains(response, reverse("food:restaurant_detail", args=[restaurant.pk]))
        self.assertContains(response, "08:00")
        for radius in (1, 3, 5):
            self.assertContains(response, f'<option value="{radius}">{radius} km</option>')
        data = response.context["restaurants"][0]
        self.assertEqual((data["lat"], data["lng"]), (-6.36, 106.83))

    def test_only_active_restaurants_with_valid_coordinates_are_mapped(self):
        valid = Restaurant.objects.create(nama="Valid", alamat="A", lat=0, lng=0)
        Restaurant.objects.create(nama="Inactive", alamat="B", lat=0, lng=0, is_active=False)
        Restaurant.objects.create(nama="Missing", alamat="C", lat=None, lng=106.8)
        Restaurant.objects.create(nama="Out of bounds", alamat="D", lat=91, lng=181)
        response = self.client.get("/map/")
        self.assertEqual([r["id"] for r in response.context["restaurants"]], [valid.pk])

    @patch("map.views._load_dummy_data", return_value={"restaurants": []})
    def test_empty_map_is_usable(self, load_dummy):
        response = self.client.get("/map/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Belum ada restoran dengan koordinat yang valid.")
        self.assertContains(response, 'id="restaurant-map"')

    @patch("map.views._load_dummy_data")
    def test_dummy_fallback_filters_inactive_and_invalid_coordinates(self, load_dummy):
        load_dummy.return_value = {"restaurants": [
            {"id": 1, "nama": "Dummy", "alamat": "A", "lat": -6.3, "lng": 106.8},
            {"id": 2, "nama": "Inactive", "lat": 0, "lng": 0, "is_active": False},
            {"id": 3, "nama": "Invalid", "lat": "NaN", "lng": 106},
            {"id": 4, "nama": "Missing", "lat": None, "lng": 106},
        ]}
        response = self.client.get("/map/")
        self.assertEqual([r["id"] for r in response.context["restaurants"]], [1])

    def test_restaurant_content_is_escaped_in_html_and_json(self):
        Restaurant.objects.create(
            nama='</script><script>alert("x")</script>', alamat="<img src=x>",
            lat=0, lng=0,
        )
        response = self.client.get("/map/")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, r"\u003C/script\u003E")
        self.assertContains(response, "&lt;img src=x&gt;")

    @patch("map.views._load_dummy_data")
    def test_existing_active_rows_do_not_fall_back_when_coordinates_are_missing(self, load_dummy):
        Restaurant.objects.create(nama="No location", alamat="A")
        response = self.client.get("/map/")
        self.assertEqual(response.context["restaurants"], [])
        load_dummy.assert_not_called()
