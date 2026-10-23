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

from .models import Order

ACTIVE = (Order.Status.PENDING, Order.Status.CONFIRMED)
MAX_PER_ORDER = 3
PICKUP_GRACE = datetime.timedelta(minutes=15)


class OrderError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def expire_stale_orders(queryset=None):
    cutoff = timezone.now() - PICKUP_GRACE
    stale = (queryset if queryset is not None else Order.objects.all()).filter(
        status__in=ACTIVE, surprise_box__pickup_end__lt=cutoff
    )
    return Order.objects.filter(pk__in=list(stale.values_list("pk", flat=True))).update(status=Order.Status.EXPIRED)


def _within_pickup_window(box, now=None):
    now = now or timezone.now()
    if box.pickup_start and now < box.pickup_start:
        return False
    if box.pickup_end and now > box.pickup_end:
        return False
    return True


def _require_owner(order, user):
    if order.pembeli_id != user.id:
        raise PermissionDenied("Kamu tidak berhak mengakses pesanan ini.")


def _require_seller(order, user):
    box = order.surprise_box
    owner_id = box.restaurant.owner_id if box else None
    if not (user.is_staff or (owner_id and owner_id == user.id)):
        raise PermissionDenied("Hanya pemilik restoran yang boleh menyelesaikan pesanan.")


def _available_boxes():
    return SurpriseBox.objects.select_related("restaurant").filter(is_active=True, restaurant__is_active=True)


def _new_order(**fields):
    for _ in range(5):
        try:
            with transaction.atomic():
                return Order.objects.create(kode_pickup=uuid.uuid4().hex[:8].upper(), **fields)
        except IntegrityError as exc:
            if "kode_pickup" not in str(exc):
                raise
    raise IntegrityError("Gagal membuat kode pickup unik.")


@login_required
@require_POST
def create_order(request, box_id):
    try:
        jumlah = int(request.POST.get("jumlah", 1))
    except ValueError:
        return JsonResponse({"error": "Jumlah tidak valid."}, status=400)

    if jumlah < 1:
        return JsonResponse({"error": "Jumlah harus minimal 1."}, status=400)
    if jumlah > MAX_PER_ORDER:
        return JsonResponse({"error": f"Maksimal {MAX_PER_ORDER} box per pesanan."}, status=400)

    try:
        with transaction.atomic():
            box = _available_boxes().filter(pk=box_id).first()
            if not box:
                raise OrderError("Surprise box tidak ditemukan.", 404)

            if not _within_pickup_window(box):
                raise OrderError("Di luar jendela pickup.")

            expire_stale_orders(Order.objects.filter(pembeli=request.user, surprise_box=box))
            if Order.objects.filter(pembeli=request.user, surprise_box=box, status__in=ACTIVE).exists():
                raise OrderError("Kamu sudah punya pesanan aktif untuk paket ini.", 409)

            reserved = SurpriseBox.objects.filter(pk=box.pk, stok__gte=jumlah).update(stok=F("stok") - jumlah)
            if not reserved:
                raise OrderError("Stok tidak cukup.")

            order = _new_order(pembeli=request.user, surprise_box=box, jumlah=jumlah)
    except OrderError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)
    except IntegrityError:
        return JsonResponse({"error": "Kamu sudah punya pesanan aktif untuk paket ini."}, status=409)

    return JsonResponse(
        {
            "message": "Reservasi berhasil.",
            "id": order.id,
            "kode_pickup": order.kode_pickup,
            "status": order.status,
        },
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
def cancel_order(request, order_id):
    expire_stale_orders(Order.objects.filter(pk=order_id))
    with transaction.atomic():
        order = get_object_or_404(Order, id=order_id)
        _require_owner(order, request.user)

        changed = Order.objects.filter(pk=order.pk, status__in=ACTIVE).update(status=Order.Status.CANCELLED)
        if not changed:
            return JsonResponse({"error": "Pesanan ini sudah tidak bisa dibatalkan."}, status=400)

        if order.surprise_box_id:
            SurpriseBox.objects.filter(pk=order.surprise_box_id).update(stok=F("stok") + order.jumlah)

    return JsonResponse({"message": "Pesanan dibatalkan.", "status": Order.Status.CANCELLED})


@login_required
@require_POST
def complete_order(request, order_id):
    expire_stale_orders(Order.objects.filter(pk=order_id))
    order = get_object_or_404(Order.objects.select_related("surprise_box__restaurant"), id=order_id)
    _require_seller(order, request.user)

    changed = Order.objects.filter(pk=order.pk, status__in=ACTIVE).update(status=Order.Status.COMPLETED)
    if not changed:
        return JsonResponse({"error": "Pesanan ini tidak bisa diselesaikan."}, status=400)

    return JsonResponse({"message": "Pesanan ditandai selesai diambil.", "status": Order.Status.COMPLETED})


@login_required
def order_confirmation(request, order_id):
    expire_stale_orders(Order.objects.filter(pk=order_id))
    order = get_object_or_404(Order.objects.select_related("surprise_box__restaurant"), id=order_id)
    _require_owner(order, request.user)

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
