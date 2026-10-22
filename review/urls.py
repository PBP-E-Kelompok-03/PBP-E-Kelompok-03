
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
]
