from rest_framework import serializers

from food.models import SurpriseBox

from .forms import MAX_PER_ORDER
from .models import Order


class BoxSerializer(serializers.ModelSerializer):
    restoran = serializers.CharField(source="restaurant.nama")
    alamat = serializers.CharField(source="restaurant.alamat")

    class Meta:
        model = SurpriseBox
        fields = ["id", "nama_paket", "restoran", "alamat", "harga_normal", "harga_diskon", "stok", "image_url"]


class OrderSerializer(serializers.ModelSerializer):
    nama_paket = serializers.CharField(source="surprise_box.nama_paket", read_only=True, default="")
    restoran = serializers.CharField(source="surprise_box.restaurant.nama", read_only=True, default="")
    alamat = serializers.CharField(source="surprise_box.restaurant.alamat", read_only=True, default="")
    pembeli = serializers.CharField(source="pembeli.username", read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "nama_paket", "restoran", "alamat", "pembeli", "jumlah",
            "harga_satuan", "total", "status", "kode_pickup", "dibuat_pada", "kedaluwarsa_pada",
        ]

    def get_total(self, order):
        return f"{order.jumlah * order.harga_satuan:.2f}"

    def to_representation(self, order):
        """kode pickup hanya dikirim ke pembeli pemilik pesanan"""
        data = super().to_representation(order)
        request = self.context.get("request")
        if request is None or request.user.id != order.pembeli_id:
            data.pop("kode_pickup")
        return data


class OrderCreateSerializer(serializers.Serializer):
    box_id = serializers.IntegerField()
    jumlah = serializers.IntegerField(min_value=1, max_value=MAX_PER_ORDER, default=1)


class PickupCodeSerializer(serializers.Serializer):
    kode_pickup = serializers.CharField()

    def validate_kode_pickup(self, value):
        return value.upper()
