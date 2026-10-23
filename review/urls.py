
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

]
