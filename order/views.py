import json
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Order


def _load_surprise_boxes():
    """
    Baca surprise box dari dummy data (fixtures/dummy_data.json).
    TODO: ganti jadi query food.SurpriseBox begitu modelnya ada (lihat docs/ERD.md).
    """
    fixture_path = Path(settings.BASE_DIR) / "fixtures" / "dummy_data.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    return {box["id"]: box for box in data.get("surprise_boxes", []) if box.get("is_active", True)}


def _remaining_stock(box):
    reserved = (
        Order.objects.filter(surprise_box_id=box["id"])
        .exclude(status=Order.Status.CANCELLED)
        .aggregate(total=Sum("jumlah"))["total"]
        or 0
    )
    return box["stok"] - reserved


@login_required
@require_POST
def create_order(request, box_id):
    boxes = _load_surprise_boxes()
    box = boxes.get(box_id)
    if not box:
        return JsonResponse({"error": "Surprise box tidak ditemukan."}, status=404)

    try:
        jumlah = int(request.POST.get("jumlah", 1))
    except ValueError:
        return JsonResponse({"error": "Jumlah tidak valid."}, status=400)

    if jumlah < 1:
        return JsonResponse({"error": "Jumlah harus minimal 1."}, status=400)

    with transaction.atomic():
        if jumlah > _remaining_stock(box):
            return JsonResponse({"error": "Stok tidak cukup."}, status=400)

        order = Order.objects.create(
            pembeli=request.user,
            surprise_box_id=box_id,
            jumlah=jumlah,
            kode_pickup=uuid.uuid4().hex[:8].upper(),
        )

    return JsonResponse(
        {
            "message": "Reservasi berhasil.",
            "kode_pickup": order.kode_pickup,
            "status": order.status,
        },
        status=201,
    )


@login_required
def order_history(request):
    orders = Order.objects.filter(pembeli=request.user).order_by("-dibuat_pada")
    boxes = _load_surprise_boxes()
    order_list = [{"order": order, "box": boxes.get(order.surprise_box_id)} for order in orders]
    return render(request, "order/history.html", {"order_list": order_list})


@login_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.pembeli_id != request.user.id:
        raise PermissionDenied("Kamu tidak berhak membatalkan pesanan ini.")

    order.status = Order.Status.CANCELLED
    order.save()
    return JsonResponse({"message": "Pesanan dibatalkan.", "status": order.status})
