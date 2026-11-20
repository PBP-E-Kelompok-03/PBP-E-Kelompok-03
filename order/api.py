import uuid

from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from food.models import SurpriseBox

from .models import Order
from .serializers import BoxSerializer, OrderCreateSerializer, OrderSerializer, PickupCodeSerializer
from .views import ACTIVE, _available_boxes, _cancel, expire_stale_orders


def _fail(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({"error": message}, status=code)


class BoxViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BoxSerializer

    def get_queryset(self):
        return _available_boxes().filter(stok__gt=0)


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        user = self.request.user
        orders = Order.objects.select_related("surprise_box__restaurant", "pembeli")
        if user.is_staff:
            pass
        elif user.is_partner:
            orders = orders.filter(surprise_box__restaurant__owner=user)
        else:
            orders = orders.filter(pembeli=user)
        expire_stale_orders(orders)
        return orders.order_by("-dibuat_pada")

    def get_seller_order(self):
        order = self.get_object()
        box = order.surprise_box
        if not (self.request.user.is_staff or (box and box.restaurant.owner_id == self.request.user.id)):
            raise PermissionDenied("Hanya pemilik restoran yang boleh mengelola pesanan ini.")
        return order

    def create(self, request):
        if not request.user.is_buyer:
            return _fail("Akun mitra tidak bisa memesan. Gunakan akun pembeli.", status.HTTP_403_FORBIDDEN)
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        jumlah = serializer.validated_data["jumlah"]
        try:
            with transaction.atomic():
                box = _available_boxes().filter(pk=serializer.validated_data["box_id"]).first()
                if not box:
                    return _fail("Surprise box tidak ditemukan.", status.HTTP_404_NOT_FOUND)
                expire_stale_orders(Order.objects.filter(surprise_box=box))
                if Order.objects.filter(pembeli=request.user, surprise_box=box, status__in=ACTIVE).exists():
                    return _fail("Kamu sudah punya pesanan aktif untuk paket ini.", status.HTTP_409_CONFLICT)
                reserved = SurpriseBox.objects.filter(pk=box.pk, stok__gte=jumlah).update(stok=F("stok") - jumlah)
                if not reserved:
                    return _fail("Stok tidak cukup.")
                order = Order.objects.create(
                    pembeli=request.user,
                    surprise_box=box,
                    jumlah=jumlah,
                    harga_satuan=box.harga_diskon,
                    kode_pickup=uuid.uuid4().hex[:8].upper(),
                )
        except IntegrityError:
            return _fail("Kamu sudah punya pesanan aktif untuk paket ini.", status.HTTP_409_CONFLICT)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.pembeli_id != request.user.id:
            raise PermissionDenied("Kamu tidak berhak mengakses pesanan ini.")
        _, changed = _cancel(order.pk, [Order.Status.PENDING])
        if not changed:
            return _fail("Pesanan ini sudah tidak bisa dibatalkan.")
        return Response({"message": "Pesanan dibatalkan.", "status": Order.Status.CANCELLED})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        order = self.get_seller_order()
        _, changed = _cancel(order.pk, ACTIVE)
        if not changed:
            return _fail("Pesanan ini tidak bisa ditolak.")
        return Response({"message": "Pesanan ditolak.", "status": Order.Status.CANCELLED})

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_seller_order()
        changed = Order.objects.filter(pk=order.pk, status=Order.Status.PENDING).update(status=Order.Status.CONFIRMED)
        if not changed:
            return _fail("Pesanan ini tidak bisa diterima.")
        return Response({"message": "Pesanan diterima.", "status": Order.Status.CONFIRMED})

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        order = self.get_seller_order()
        serializer = PickupCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["kode_pickup"] != order.kode_pickup:
            return _fail("Kode pickup tidak cocok.")
        changed = Order.objects.filter(pk=order.pk, status=Order.Status.CONFIRMED).update(status=Order.Status.COMPLETED)
        if not changed:
            return _fail("Pesanan ini tidak bisa diselesaikan.")
        return Response({"message": "Pesanan ditandai selesai diambil.", "status": Order.Status.COMPLETED})
