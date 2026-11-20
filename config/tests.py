from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from food.models import Restaurant, SurpriseBox


class SharedLayoutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dyah", password="pass12345")
        owner = User.objects.create_user(username="mitra", password="pass12345", role=User.Role.PARTNER)
        restaurant = Restaurant.objects.create(nama="Kedai Layout", alamat="Jl. Test", owner=owner)
        SurpriseBox.objects.create(
            restaurant=restaurant, nama_paket="Paket Layout", harga_normal=40000, harga_diskon=20000, stok=3
        )
        self.restaurant = restaurant

    def public_pages(self):
        return [
            reverse("landing"),
            reverse("food:list"),
            reverse("food:restaurant_detail", args=[self.restaurant.id]),
            reverse("map:map"),
            reverse("accounts:login"),
            reverse("accounts:register"),
        ]

    def test_every_public_page_has_exactly_one_footer_and_navbar(self):
        for url in self.public_pages():
            html = self.client.get(url).content.decode()
            self.assertEqual(html.count("<footer"), 1, url)
            self.assertEqual(html.count('<nav class="navbar"'), 1, url)

    def test_logged_in_pages_share_the_same_footer(self):
        self.client.login(username="dyah", password="pass12345")
        for url in (reverse("order:history"), reverse("accounts:profile")):
            html = self.client.get(url).content.decode()
            self.assertEqual(html.count("<footer"), 1, url)
            self.assertIn("PBP E Kelompok 03", html, url)

    def test_footer_cara_kerja_link_works_from_other_pages(self):
        html = self.client.get(reverse("food:list")).content.decode()
        self.assertIn(reverse("landing") + "#cara-kerja", html)

    def test_navbar_shows_login_for_guest_and_profile_for_user(self):
        self.assertContains(self.client.get(reverse("landing")), reverse("accounts:login"))
        self.client.login(username="dyah", password="pass12345")
        self.assertContains(self.client.get(reverse("landing")), reverse("accounts:profile"))
