
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from selenium import webdriver
from selenium.webdriver.common.by import By

from order.models import Order
from . import views
from .forms import ReviewForm

import sys
from unittest import skipUnless


# ============================================================
# BAGIAN 1 — UNIT TEST BACKEND REVIEW
# ============================================================

class TestReviewBackend(SimpleTestCase):

    def setUp(self):
        # Membuat request simulasi tanpa browser
        self.factory = RequestFactory()

        # Akun pembeli pemilik review
        self.buyer = SimpleNamespace(
            pk=7,
            username="khansa",
            is_authenticated=True,
            is_buyer=True,
            is_partner=False
        )

        # Akun pembeli lain
        self.other_buyer = SimpleNamespace(
            pk=8,
            username="pembeli_lain",
            is_authenticated=True,
            is_buyer=True,
            is_partner=False
        )

        # Akun pemilik restoran
        self.partner = SimpleNamespace(
            pk=21,
            is_authenticated=True,
            is_buyer=False,
            is_partner=True
        )

        # Restoran simulasi
        self.restaurant = SimpleNamespace(
            nama="Restoran A",
            owner_id=21
        )

        # Order yang sudah selesai
        self.order = SimpleNamespace(
            pembeli=self.buyer,
            pembeli_id=7,
            status=Order.Status.COMPLETED,
            surprise_box_id=2,
            surprise_box=SimpleNamespace(
                restaurant=self.restaurant
            )
        )

        # Review simulasi
        self.review = SimpleNamespace(
            id=5,
            pk=5,
            order=self.order,
            rating=5,
            comment="Makanannya enak!",
            owner_reply="",
            active=True,
            created_at=datetime(2026, 10, 26),
            save=Mock()
        )

    # ========================================================
    # TEST 1 — Hapus review sebelum dibalas
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_hapus_sebelum_dibalas(self, mock_get, mock_filter):

        mock_get.return_value = self.review

        # Database berhasil menjalankan soft delete
        mock_filter.return_value.update.return_value = 1

        request = self.factory.post("/review/delete/5/")
        request.user = self.buyer

        response = views.delete_review(request, 5)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])

        # Hanya review aktif dan belum dibalas
        mock_filter.assert_called_once_with(
            pk=5,
            active=True,
            owner_reply=""
        )

        # Soft delete, bukan delete permanen
        mock_filter.return_value.update.assert_called_once_with(
            active=False
        )

    # ========================================================
    # TEST 2 — Hapus setelah dibalas harus ditolak
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_hapus_setelah_dibalas(self, mock_get, mock_filter):

        self.review.owner_reply = "Terima kasih!"
        mock_get.return_value = self.review

        request = self.factory.post("/review/delete/5/")
        request.user = self.buyer

        response = views.delete_review(request, 5)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(json.loads(response.content)["success"])

        # Tidak boleh mengubah database
        mock_filter.assert_not_called()

    # ========================================================
    # TEST 3 — Edit sebelum dibalas
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.ReviewForm")
    @patch("review.views.get_object_or_404")
    def test_edit_sebelum_dibalas(
        self, mock_get, mock_form, mock_filter
    ):

        mock_get.return_value = self.review

        # Form simulasi valid
        mock_form.return_value.is_valid.return_value = True
        mock_form.return_value.cleaned_data = {
            "rating": 4,
            "comment": "Komentar diperbarui"
        }

        # Database berhasil melakukan UPDATE
        mock_filter.return_value.update.return_value = 1

        request = self.factory.post(
            "/review/update/5/",
            {
                "rating": "4",
                "comment": "Komentar diperbarui"
            }
        )
        request.user = self.buyer

        response = views.update_review(request, 5)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])

        mock_filter.assert_called_once_with(
            pk=5,
            active=True,
            owner_reply=""
        )

        mock_filter.return_value.update.assert_called_once_with(
            rating=4,
            comment="Komentar diperbarui"
        )

    # ========================================================
    # TEST 4 — Edit setelah dibalas harus ditolak
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_edit_setelah_dibalas(self, mock_get, mock_filter):

        self.review.owner_reply = "Terima kasih!"
        mock_get.return_value = self.review

        request = self.factory.post(
            "/review/update/5/",
            {
                "rating": "3",
                "comment": "Komentar baru"
            }
        )
        request.user = self.buyer

        response = views.update_review(request, 5)

        self.assertEqual(response.status_code, 403)
        mock_filter.assert_not_called()

    # ========================================================
    # TEST 5 — Pembeli tidak boleh hapus review orang lain
    # ========================================================

    @patch("review.views.get_object_or_404")
    def test_hapus_review_orang_lain(self, mock_get):

        mock_get.return_value = self.review

        request = self.factory.post("/review/delete/5/")
        request.user = self.other_buyer

        with self.assertRaises(PermissionDenied):
            views.delete_review(request, 5)

    # ========================================================
    # TEST 6 — Restoran boleh membalas review
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_restoran_membalas(self, mock_get, mock_filter):

        mock_get.return_value = self.review

        mock_filter.return_value.update.return_value = 1

        request = self.factory.post(
            "/review/reply/5/",
            {"owner_reply": "Terima kasih!"}
        )
        request.user = self.partner

        response = views.reply_review(request, 5)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(
            data["owner_reply"],
            "Terima kasih!"
        )

        mock_filter.return_value.update.assert_called_once_with(
            owner_reply="Terima kasih!"
        )

    # ========================================================
    # TEST 7 — Tombol Edit/Hapus sesuai hak akses
    # ========================================================

    @patch("review.views.Review.objects.filter")
    def test_can_manage_review(self, mock_filter):

        queryset = MagicMock()
        mock_filter.return_value = queryset

        queryset.select_related.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.aggregate.return_value = {
            "rating__avg": 5
        }
        queryset.count.return_value = 1
        queryset.__getitem__.return_value = [self.review]

        request = self.factory.get(
            "/review/restaurant/1/reviews/"
        )
        request.user = self.buyer

        # Review sendiri, belum dibalas
        response = views.restaurant_reviews(request, 1)
        data = json.loads(response.content)

        self.assertEqual(data["reviews"][0]["id"], 5)
        self.assertTrue(data["reviews"][0]["can_manage"])

        # Review sudah dibalas
        self.review.owner_reply = "Terima kasih!"

        response = views.restaurant_reviews(request, 1)
        data = json.loads(response.content)

        self.assertFalse(data["reviews"][0]["can_manage"])

        # Review milik orang lain
        self.review.owner_reply = ""
        request.user = self.other_buyer

        response = views.restaurant_reviews(request, 1)
        data = json.loads(response.content)

        self.assertFalse(data["reviews"][0]["can_manage"])

    # ========================================================
    # TEST 8 — Restoran membalas bersamaan dengan Edit
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.ReviewForm")
    @patch("review.views.get_object_or_404")
    def test_edit_saat_balasan_baru_masuk(
        self, mock_get, mock_form, mock_filter
    ):

        mock_get.return_value = self.review

        mock_form.return_value.is_valid.return_value = True
        mock_form.return_value.cleaned_data = {
            "rating": 3,
            "comment": "Komentar baru"
        }

        # Simulasi UPDATE gagal karena syarat
        # owner_reply="" sudah tidak terpenuhi
        mock_filter.return_value.update.return_value = 0

        request = self.factory.post(
            "/review/update/5/",
            {
                "rating": "3",
                "comment": "Komentar baru"
            }
        )
        request.user = self.buyer

        response = views.update_review(request, 5)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(json.loads(response.content)["success"])

    # ========================================================
    # TEST 9 — Restoran membalas bersamaan dengan Hapus
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_hapus_saat_balasan_baru_masuk(
        self, mock_get, mock_filter
    ):

        mock_get.return_value = self.review

        # Database menolak UPDATE bersyarat
        mock_filter.return_value.update.return_value = 0

        request = self.factory.post("/review/delete/5/")
        request.user = self.buyer

        response = views.delete_review(request, 5)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(json.loads(response.content)["success"])

    # ========================================================
    # TEST 10 — Edit dengan data tidak valid
    # ========================================================

    @patch("review.views.ReviewForm")
    @patch("review.views.get_object_or_404")
    def test_edit_data_tidak_valid(self, mock_get, mock_form):

        mock_get.return_value = self.review

        mock_form.return_value.is_valid.return_value = False
        mock_form.return_value.errors = {
            "rating": ["Nilai tidak valid"]
        }

        request = self.factory.post(
            "/review/update/5/",
            {
                "rating": "9",
                "comment": "Tes"
            }
        )
        request.user = self.buyer

        response = views.update_review(request, 5)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content)["success"])

    # ========================================================
    # TEST 11 — Rating di luar 1 sampai 5 ditolak
    # ========================================================

    def test_form_rating_di_luar_rentang(self):

        form = ReviewForm(data={
            "rating": "6",
            "comment": "Makanannya enak"
        })

        self.assertFalse(form.is_valid())
        self.assertIn("rating", form.errors)

    # ========================================================
    # TEST 12 — Komentar kosong ditolak
    # ========================================================

    def test_form_komentar_kosong(self):

        form = ReviewForm(data={
            "rating": "5",
            "comment": "   "
        })

        self.assertFalse(form.is_valid())
        self.assertIn("comment", form.errors)

    # ========================================================
    # TEST 13 — Order completed boleh membuat review
    # ========================================================

    @patch("review.views.transaction.atomic")
    @patch("review.views.Review.objects.filter")
    @patch("review.views.ReviewForm")
    @patch("review.views.get_object_or_404")
    def test_buat_review_order_completed(
        self,
        mock_get,
        mock_form,
        mock_filter,
        mock_atomic
    ):

        mock_get.return_value = self.order

        # Belum ada review untuk order ini
        mock_filter.return_value.exists.return_value = False

        # Form valid
        mock_form.return_value.is_valid.return_value = True

        # Simulasi form.save(commit=False)
        mock_form.return_value.save.return_value = self.review

        request = self.factory.post(
            "/review/create/1/",
            {
                "rating": "5",
                "comment": "Enak!"
            }
        )
        request.user = self.buyer

        response = views.create_review(request, 1)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])

        # Review harus disimpan
        self.review.save.assert_called_once()

        # Review harus dikaitkan dengan order
        self.assertIs(self.review.order, self.order)

    # ========================================================
    # TEST 14 — Order pending tidak boleh direview
    # ========================================================

    @patch("review.views.get_object_or_404")
    def test_buat_review_order_pending_ditolak(self, mock_get):

        self.order.status = Order.Status.PENDING
        mock_get.return_value = self.order

        request = self.factory.post(
            "/review/create/1/",
            {
                "rating": "5",
                "comment": "Enak!"
            }
        )
        request.user = self.buyer

        with self.assertRaises(PermissionDenied):
            views.create_review(request, 1)

    # ========================================================
    # TEST 15 — Restoran lain tidak boleh membalas
    # ========================================================

    @patch("review.views.get_object_or_404")
    def test_mitra_lain_tidak_boleh_membalas(self, mock_get):

        mock_get.return_value = self.review

        # Mitra lain yang bukan pemilik restoran
        other_partner = SimpleNamespace(
            pk=99,
            is_authenticated=True,
            is_buyer=False,
            is_partner=True
        )

        request = self.factory.post(
            "/review/reply/5/",
            {"owner_reply": "Halo"}
        )
        request.user = other_partner

        with self.assertRaises(PermissionDenied):
            views.reply_review(request, 5)

    # ========================================================
    # TEST 16 — Satu order tidak boleh punya dua review
    # ========================================================

    @patch("review.views.transaction.atomic")
    @patch("review.views.Review.objects.filter")
    @patch("review.views.ReviewForm")
    @patch("review.views.get_object_or_404")
    def test_review_duplikat_ditolak(
        self,
        mock_get,
        mock_form,
        mock_filter,
        mock_atomic
    ):

        mock_get.return_value = self.order

        mock_form.return_value.is_valid.return_value = True

        # Sudah ada review untuk order tersebut
        mock_filter.return_value.exists.return_value = True

        request = self.factory.post(
            "/review/create/1/",
            {
                "rating": "5",
                "comment": "Review kedua"
            }
        )
        request.user = self.buyer

        response = views.create_review(request, 1)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(json.loads(response.content)["success"])

        # Review kedua tidak boleh disimpan
        mock_form.return_value.save.assert_not_called()

    # ========================================================
    # TEST 17 — Tidak boleh review pesanan orang lain
    # ========================================================

    @patch("review.views.get_object_or_404")
    def test_review_order_orang_lain_ditolak(self, mock_get):

        mock_get.return_value = self.order

        request = self.factory.post(
            "/review/create/1/",
            {
                "rating": "5",
                "comment": "Enak!"
            }
        )
        request.user = self.other_buyer

        with self.assertRaises(PermissionDenied):
            views.create_review(request, 1)

    # ========================================================
    # TEST 18 — Restoran tidak boleh membalas kosong
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_balasan_restoran_kosong_ditolak(
        self, mock_get, mock_filter
    ):

        mock_get.return_value = self.review

        request = self.factory.post(
            "/review/reply/5/",
            {"owner_reply": "   "}
        )
        request.user = self.partner

        response = views.reply_review(request, 5)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content)["success"])

        mock_filter.assert_not_called()

    # ========================================================
    # TEST 19 — Balasan lebih dari 1000 karakter ditolak
    # ========================================================

    @patch("review.views.Review.objects.filter")
    @patch("review.views.get_object_or_404")
    def test_balasan_restoran_terlalu_panjang(
        self, mock_get, mock_filter
    ):

        mock_get.return_value = self.review

        request = self.factory.post(
            "/review/reply/5/",
            {"owner_reply": "A" * 1001}
        )
        request.user = self.partner

        response = views.reply_review(request, 5)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content)["success"])

        mock_filter.assert_not_called()

    # ========================================================
    # TEST 20 — Tidak boleh edit review orang lain
    # ========================================================

    @patch("review.views.get_object_or_404")
    def test_edit_review_orang_lain_ditolak(self, mock_get):

        mock_get.return_value = self.review

        request = self.factory.post(
            "/review/update/5/",
            {
                "rating": "2",
                "comment": "Komentar orang lain"
            }
        )
        request.user = self.other_buyer

        with self.assertRaises(PermissionDenied):
            views.update_review(request, 5)


# ============================================================
# BAGIAN 2 — SELENIUM SAFARI
# ============================================================

@skipUnless(sys.platform == "darwin", "Safari hanya tersedia di macOS")
class TestReviewSelenium(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Membuka browser Safari
        try:
            cls.browser = webdriver.Safari()
            cls.browser.set_script_timeout(10)
        except Exception:
            super().tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):

        # Menutup browser Safari setelah pengujian
        try:
            cls.browser.quit()
        finally:
            super().tearDownClass()

    # ========================================================
    # TEST 21 — Safari berhasil membuka aplikasi
    # ========================================================

    def test_browser_membuka_aplikasi(self):

        self.browser.get(
            self.live_server_url + "/"
        )

        body = self.browser.find_element(
            By.TAG_NAME,
            "body"
        )

        self.assertTrue(body.is_displayed())

    # ========================================================
    # TEST 22 — Safari berhasil mengambil JSON review
    # ========================================================

    def test_browser_mengambil_data_review(self):

        # Endpoint restoran yang tidak memiliki review
        url = (
            self.live_server_url
            + "/review/restaurant/999999/reviews/"
        )

        self.browser.get(url)

        # AJAX menggunakan fetch dari Safari
        data = self.browser.execute_async_script("""
            const selesai = arguments[arguments.length - 1];

            fetch(window.location.href)
                .then(response => response.json())
                .then(data => selesai(data))
                .catch(error => selesai({
                    error: String(error)
                }));
        """)

        # Pastikan respons tidak mengandung error
        self.assertNotIn("error", data)

        # Pastikan struktur JSON sesuai API Django
        self.assertIn("rata_rata", data)
        self.assertIn("jumlah_ulasan", data)
        self.assertIn("reviews", data)

        # Restoran simulasi tidak memiliki review
        self.assertEqual(data["jumlah_ulasan"], 0)
        self.assertEqual(data["reviews"], [])
