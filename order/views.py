import uuid

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from food.models import SurpriseBox

from .decorators import owner_required, seller_required
from .forms import MAX_PER_ORDER, OrderCreateForm, PickupCodeForm
from .models import ORDER_TTL, Order

ACTIVE = (Order.Status.PENDING, Order.Status.CONFIRMED)


def expire_stale_orders(orders=None):
    """tandai pesanan aktif yang lewat 24 jam jadi expired dan balikin stoknya"""
    orders = Order.objects.all() if orders is None else orders
    cutoff = timezone.now() - ORDER_TTL
    expired = 0
    for order in orders.filter(status__in=ACTIVE, dibuat_pada__lt=cutoff):
        with transaction.atomic():
            changed = Order.objects.filter(pk=order.pk, status__in=ACTIVE).update(status=Order.Status.EXPIRED)
            if changed and order.surprise_box_id:
                SurpriseBox.objects.filter(pk=order.surprise_box_id).update(stok=F("stok") + order.jumlah)
        expired += changed
    return expired


def _available_boxes():
    """box dan restoran yang masih aktif"""
    return SurpriseBox.objects.select_related("restaurant").filter(is_active=True, restaurant__is_active=True)


def _error(message, status=400):
    """balikin json error untuk ajax"""
    return JsonResponse({"error": message}, status=status)


@login_required
@require_POST
def create_order(request, box_id):
    """ajax pembeli: kurangi stok, simpan harga, buat pesanan dengan kode pickup"""
    if not request.user.is_buyer:
        return _error("Akun mitra tidak bisa memesan. Gunakan akun pembeli.", 403)
    form = OrderCreateForm(request.POST if "jumlah" in request.POST else {"jumlah": 1})
    if not form.is_valid():
        return _error(form.errors["jumlah"][0])
    jumlah = form.cleaned_data["jumlah"]

    try:
        with transaction.atomic():
            box = _available_boxes().filter(pk=box_id).first()
            if not box:
                return _error("Surprise box tidak ditemukan.", 404)

            expire_stale_orders(Order.objects.filter(surprise_box=box))
            if Order.objects.filter(pembeli=request.user, surprise_box=box, status__in=ACTIVE).exists():
                return _error("Kamu sudah punya pesanan aktif untuk paket ini.", 409)

            reserved = SurpriseBox.objects.filter(pk=box.pk, stok__gte=jumlah).update(stok=F("stok") - jumlah)
            if not reserved:
                return _error("Stok tidak cukup.")

            order = Order.objects.create(
                pembeli=request.user,
                surprise_box=box,
                jumlah=jumlah,
                harga_satuan=box.harga_diskon,
                kode_pickup=uuid.uuid4().hex[:8].upper(),
            )
    except IntegrityError:
        return _error("Kamu sudah punya pesanan aktif untuk paket ini.", 409)

    return JsonResponse(
        {"message": "Reservasi berhasil.", "id": order.id, "kode_pickup": order.kode_pickup, "status": order.status},
        status=201,
    )


@login_required
def checkout_view(request, box_id):
    """halaman checkout, khusus pembeli"""
    if not request.user.is_buyer:
        raise PermissionDenied("Akun mitra tidak bisa memesan. Gunakan akun pembeli.")
    box = _available_boxes().filter(pk=box_id).first()
    if not box:
        return render(request, "order/checkout.html", {"box": None}, status=404)

    return render(
        request,
        "order/checkout.html",
        {
            "box": box,
            "restaurant": box.restaurant,
            "remaining_stock": box.stok,
            "max_qty": min(box.stok, MAX_PER_ORDER),
        },
    )


@login_required
def order_history(request):
    """riwayat pesanan milik pembeli"""
    expire_stale_orders(Order.objects.filter(pembeli=request.user))
    orders = Order.objects.filter(pembeli=request.user).select_related("surprise_box__restaurant").order_by("-dibuat_pada")
    order_list = [{"order": order, "box": order.surprise_box} for order in orders]
    return render(request, "order/history.html", {"order_list": order_list})


def _cancel(order_id, from_statuses):
    """batalkan pesanan kalau statusnya masih di from_statuses, lalu balikin stok"""
    with transaction.atomic():
        order = get_object_or_404(Order, id=order_id)
        changed = Order.objects.filter(pk=order.pk, status__in=from_statuses).update(
            status=Order.Status.CANCELLED
        )
        if changed and order.surprise_box_id:
            SurpriseBox.objects.filter(pk=order.surprise_box_id).update(stok=F("stok") + order.jumlah)
    return order, changed


@login_required
@require_POST
@owner_required
def cancel_order(request, order_id):
    """ajax pembeli: batalkan pesanan yang masih pending"""
    expire_stale_orders(Order.objects.filter(pk=order_id))
    order, changed = _cancel(order_id, [Order.Status.PENDING])
    if not changed:
        msg = (
            "Pesanan sudah diterima restoran dan tidak bisa dibatalkan."
            if order.status == Order.Status.CONFIRMED
            else "Pesanan ini sudah tidak bisa dibatalkan."
        )
        return JsonResponse({"error": msg}, status=400)
    return JsonResponse({"message": "Pesanan dibatalkan.", "status": Order.Status.CANCELLED})


@login_required
@require_POST
@seller_required
def reject_order(request, order_id):
    """ajax penjual: tolak pesanan pending atau confirmed (jadi cancelled)"""
    expire_stale_orders(Order.objects.filter(pk=order_id))
    _, changed = _cancel(order_id, ACTIVE)
    if not changed:
        return JsonResponse({"error": "Pesanan ini tidak bisa ditolak."}, status=400)
    return JsonResponse({"message": "Pesanan ditolak.", "status": Order.Status.CANCELLED})


@login_required
@require_POST
@seller_required
def confirm_order(request, order_id):
    """ajax penjual: terima pesanan pending jadi confirmed"""
    expire_stale_orders(Order.objects.filter(pk=order_id))
    changed = Order.objects.filter(pk=order_id, status=Order.Status.PENDING).update(
        status=Order.Status.CONFIRMED
    )
    if not changed:
        return JsonResponse({"error": "Pesanan ini tidak bisa diterima."}, status=400)
    return JsonResponse({"message": "Pesanan diterima.", "status": Order.Status.CONFIRMED})


@login_required
@require_POST
@seller_required
def complete_order(request, order_id):
    """ajax penjual: cocokkan kode pickup, confirmed jadi completed"""
    expire_stale_orders(Order.objects.filter(pk=order_id))
    order = get_object_or_404(Order, id=order_id)

    form = PickupCodeForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": form.errors["kode_pickup"][0]}, status=400)
    if form.cleaned_data["kode_pickup"] != order.kode_pickup:
        return JsonResponse({"error": "Kode pickup tidak cocok."}, status=400)

    changed = Order.objects.filter(pk=order.pk, status=Order.Status.CONFIRMED).update(
        status=Order.Status.COMPLETED
    )
    if not changed:
        msg = (
            "Terima pesanan terlebih dahulu."
            if order.status == Order.Status.PENDING
            else "Pesanan ini tidak bisa diselesaikan."
        )
        return JsonResponse({"error": msg}, status=400)

    return JsonResponse({"message": "Pesanan ditandai selesai diambil.", "status": Order.Status.COMPLETED})


@login_required
@owner_required
def order_confirmation(request, order_id):
    """halaman voucher pesanan milik pembeli"""
    expire_stale_orders(Order.objects.filter(pk=order_id))
    order = get_object_or_404(Order.objects.select_related("surprise_box__restaurant"), id=order_id)

    box = order.surprise_box
    restaurant = box.restaurant if box else None
    return render(request, "order/confirmation.html", {"order": order, "box": box, "restaurant": restaurant})


@login_required
def incoming_orders(request):
    """halaman pesanan masuk untuk mitra, dipisah aktif dan selesai"""
    orders = Order.objects.select_related("surprise_box__restaurant", "pembeli")
    expire_stale_orders()
    if not request.user.is_staff:
        if not request.user.is_partner:
            raise PermissionDenied("Halaman ini khusus mitra restoran.")
        orders = orders.filter(surprise_box__restaurant__owner=request.user)

    orders = orders.order_by("-dibuat_pada")
    active = [o for o in orders if o.status in ACTIVE]
    done = [o for o in orders if o.status not in ACTIVE]
    return render(request, "order/incoming.html", {"active_orders": active, "done_orders": done})
