from django.contrib import admin
from .models import Restaurant, SurpriseBox


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("id", "nama", "owner", "alamat", "jam_buka", "jam_tutup", "is_active", "dibuat_pada")
    list_filter = ("is_active", "jam_buka", "jam_tutup")
    search_fields = ("nama", "alamat", "owner__username")


@admin.register(SurpriseBox)
class SurpriseBoxAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nama_paket",
        "restaurant",
        "harga_normal",
        "harga_diskon",
        "stok",
        "pickup_start",
        "pickup_end",
        "is_active",
    )
    list_filter = ("is_active", "restaurant")
    search_fields = ("nama_paket", "restaurant__nama")
