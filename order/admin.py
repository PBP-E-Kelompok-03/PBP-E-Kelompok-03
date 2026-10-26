from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("kode_pickup", "pembeli", "surprise_box", "jumlah", "status", "dibuat_pada")
    list_filter = ("status",)
    search_fields = ("kode_pickup", "pembeli__username")
