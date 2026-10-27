import datetime
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
from .models import Order

ACTIVE = (Order.Status.PENDING, Order.Status.CONFIRMED)
PICKUP_GRACE = datetime.timedelta(minutes=15)


def expire_stale_orders(orders=None):
    orders = Order.objects.all() if orders is None else orders
    cutoff = timezone.now() - PICKUP_GRACE
    return orders.filter(status__in=ACTIVE, surprise_box__pickup_end__lt=cutoff).update(status=Order.Status.EXPIRED)


def _within_pickup_window(box):
    now = timezone.now()
    return (not box.pickup_start or box.pickup_start <= now) and (not box.pickup_end or now <= box.pickup_end)


def _available_boxes():
    return SurpriseBox.objects.select_related("restaurant").filter(is_active=True, restaurant__is_active=True)


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


@login_required
@require_POST
def create_order(request, box_id):
    form = OrderCreateForm(request.POST if "jumlah" in request.POST else {"jumlah": 1})
    if not form.is_valid():
        return _error(form.errors["jumlah"][0])
    jumlah = form.cleaned_data["jumlah"]

    try:
        with transaction.atomic():
            box = _available_boxes().filter(pk=box_id).first()
            if not box:
                return _error("Surprise box tidak ditemukan.", 404)
            if not _within_pickup_window(box):
                return _error("Di luar jendela pickup.")

            expire_stale_orders(Order.objects.filter(pembeli=request.user, surprise_box=box))
            if Order.objects.filter(pembeli=request.user, surprise_box=box, status__in=ACTIVE).exists():
                return _error("Kamu sudah punya pesanan aktif untuk paket ini.", 409)

            reserved = SurpriseBox.objects.filter(pk=box.pk, stok__gte=jumlah).update(stok=F("stok") - jumlah)
            if not reserved:
                return _error("Stok tidak cukup.")

            order = Order.objects.create(
                pembeli=request.user,
                surprise_box=box,
                jumlah=jumlah,
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
    expire_stale_orders(Order.objects.filter(pembeli=request.user))
    orders = Order.objects.filter(pembeli=request.user).select_related("surprise_box").order_by("-dibuat_pada")
    order_list = [{"order": order, "box": order.surprise_box} for order in orders]
    return render(request, "order/history.html", {"order_list": order_list})


@login_required
@require_POST
@owner_required
def cancel_order(request, order_id):
    expire_stale_orders(Order.objects.filter(pk=order_id))
    with transaction.atomic():
        order = get_object_or_404(Order, id=order_id)

        changed = Order.objects.filter(pk=order.pk, status=Order.Status.PENDING).update(
            status=Order.Status.CANCELLED
        )
        if not changed:
            msg = (
                "Pesanan sudah diterima restoran dan tidak bisa dibatalkan."
                if order.status == Order.Status.CONFIRMED
                else "Pesanan ini sudah tidak bisa dibatalkan."
            )
            return JsonResponse({"error": msg}, status=400)

        if order.surprise_box_id:
            SurpriseBox.objects.filter(pk=order.surprise_box_id).update(stok=F("stok") + order.jumlah)

    return JsonResponse({"message": "Pesanan dibatalkan.", "status": Order.Status.CANCELLED})


@login_required
@require_POST
@seller_required
def confirm_order(request, order_id):
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
    expire_stale_orders(Order.objects.filter(pk=order_id))
    order = get_object_or_404(Order.objects.select_related("surprise_box__restaurant"), id=order_id)

    box = order.surprise_box
    restaurant = box.restaurant if box else None
    return render(request, "order/confirmation.html", {"order": order, "box": box, "restaurant": restaurant})


@login_required
def incoming_orders(request):
    orders = Order.objects.select_related("surprise_box__restaurant", "pembeli")
    expire_stale_orders()
    if not request.user.is_staff:
        orders = orders.filter(surprise_box__restaurant__owner=request.user)
        if not request.user.restaurants.exists():
            raise PermissionDenied("Halaman ini khusus mitra restoran.")

    orders = orders.order_by("-dibuat_pada")
    active = [o for o in orders if o.status in ACTIVE]
    done = [o for o in orders if o.status not in ACTIVE]
    return render(request, "order/incoming.html", {"active_orders": active, "done_orders": done})
