
from django.urls import path
from . import views

# Nama aplikasi untuk membedakan URL dengan aplikasi lain
app_name = "review"

# Menghubungkan URL dengan fungsi pada views.py
urlpatterns = [
    # URL untuk membuat review berdasarkan ID pesanan
    path(
        "create/<int:order_id>/",
        views.create_review,
        name="create_review"
    ),
    # URL untuk menampilkan daftar ulasan dan rata-rata rating
    path(
        "box/<int:surprise_box_id>/reviews/",
        views.list_reviews,
        name="list_reviews"
    ),

    path("update/<int:review_id>/", views.update_review, name="update_review"),

    # URL untuk menghapus review menggunakan soft delete
    path(
        "delete/<int:review_id>/",
        views.delete_review,
        name="delete_review"
    ),

    # URL untuk mengambil ulasan dan rata-rata rating restoran
    path(
        "restaurant/<int:restaurant_id>/reviews/",
        views.restaurant_reviews,
        name="restaurant_reviews"
    ),

        # URL untuk menampilkan review kepada pemilik restoran
    path(
        "restaurant/<int:restaurant_id>/owner/",
        views.owner_restaurant_reviews,
        name="owner_restaurant_reviews"
    ),

    # URL untuk pemilik restoran membalas review pembeli
    path(
        "reply/<int:review_id>/",
        views.reply_review,
        name="reply_review"
    ),

]
