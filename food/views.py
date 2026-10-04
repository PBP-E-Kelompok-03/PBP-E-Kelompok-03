import datetime
import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RestaurantForm, SurpriseBoxForm
from .models import Restaurant, SurpriseBox


def _load_dummy_data():
    fixture_path = Path(settings.BASE_DIR) / "fixtures" / "dummy_data.json"
    if not fixture_path.exists():
        return {"restaurants": [], "surprise_boxes": []}
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def food_list(request):
    query = request.GET.get("q", "").strip()

    # Cek apakah database sudah ada data
    if SurpriseBox.objects.filter(is_active=True).exists():
        boxes_qs = SurpriseBox.objects.filter(
            is_active=True,
            restaurant__is_active=True,
        ).select_related("restaurant")

        if query:
            boxes_qs = boxes_qs.filter(
                Q(nama_paket__icontains=query) | Q(restaurant__nama__icontains=query)
            )

        surprise_boxes = list(boxes_qs)
        total_restaurants = Restaurant.objects.filter(is_active=True).count()
        is_from_db = True
    else:
        # Fallback dummy data jika belum migrate/seed
        data = _load_dummy_data()
        restaurants_by_id = {
            r["id"]: r for r in data.get("restaurants", []) if r.get("is_active", True)
        }
        surprise_boxes = []
        for box in data.get("surprise_boxes", []):
            if not box.get("is_active", True):
                continue
            rest = restaurants_by_id.get(box.get("restaurant_id"))
            if not rest:
                continue
            if query and query.lower() not in box["nama_paket"].lower() and query.lower() not in rest["nama"].lower():
                continue
            normal = box.get("harga_normal", 0)
            diskon = box.get("harga_diskon", 0)
            diskon_persen = round((normal - diskon) / normal * 100) if normal > 0 else 0
            surprise_boxes.append({
                **box,
                "restaurant": rest,
                "diskon_persen": diskon_persen,
            })
        total_restaurants = len(restaurants_by_id)
        is_from_db = False

    total_stock = sum(getattr(b, "stok", 0) if hasattr(b, "stok") else b.get("stok", 0) for b in surprise_boxes)

    context = {
        "surprise_boxes": surprise_boxes,
        "total_restaurants": total_restaurants,
        "total_stock": total_stock,
        "query": query,
        "is_from_db": is_from_db,
    }
    return render(request, "food/food_list.html", context)


def restaurant_detail(request, restaurant_id):
    if Restaurant.objects.filter(id=restaurant_id, is_active=True).exists():
        restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
        boxes = restaurant.surprise_boxes.filter(is_active=True)
        first_box = boxes.first()
        total_stock = sum(b.stok for b in boxes)
    else:
        data = _load_dummy_data()
        rest_dict = next((r for r in data.get("restaurants", []) if r["id"] == restaurant_id and r.get("is_active", True)), None)
        if not rest_dict:
            raise Http404("Restoran tidak ditemukan.")
        restaurant = rest_dict
        boxes = [
            b for b in data.get("surprise_boxes", [])
            if b.get("restaurant_id") == restaurant_id and b.get("is_active", True)
        ]
        for b in boxes:
            normal = b.get("harga_normal", 0)
            diskon = b.get("harga_diskon", 0)
            b["diskon_persen"] = round((normal - diskon) / normal * 100) if normal > 0 else 0
        first_box = boxes[0] if boxes else None
        total_stock = sum(b.get("stok", 0) for b in boxes)

    return render(
        request,
        "food/restaurant_detail.html",
        {
            "restaurant": restaurant,
            "boxes": boxes,
            "first_box": first_box,
            "total_stock": total_stock,
        },
    )


@login_required
def my_restaurants(request):
    restaurants = Restaurant.objects.filter(owner=request.user, is_active=True).prefetch_related("surprise_boxes")
    return render(request, "food/my_restaurants.html", {"restaurants": restaurants})


@login_required
def create_restaurant(request):
    form = RestaurantForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        restaurant = form.save(commit=False)
        restaurant.owner = request.user
        restaurant.save()
        messages.success(request, f"Restoran '{restaurant.nama}' berhasil ditambahkan.")
        return redirect("food:restaurant_detail", restaurant_id=restaurant.id)

    return render(request, "food/restaurant_form.html", {"form": form, "title": "Tambah Restoran Baru"})


@login_required
def edit_restaurant(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
    if restaurant.owner != request.user and not request.user.is_staff:
        raise PermissionDenied("Kamu tidak memiliki izin mengedit restoran ini.")

    form = RestaurantForm(request.POST or None, instance=restaurant)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Informasi restoran '{restaurant.nama}' berhasil diperbarui.")
        return redirect("food:restaurant_detail", restaurant_id=restaurant.id)

    return render(request, "food/restaurant_form.html", {"form": form, "title": f"Edit {restaurant.nama}", "restaurant": restaurant})


@login_required
def create_surprise_box(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
    if restaurant.owner != request.user and not request.user.is_staff:
        raise PermissionDenied("Kamu tidak memiliki izin mengelola paket restoran ini.")

    form = SurpriseBoxForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        box = form.save(commit=False)
        box.restaurant = restaurant
        box.save()
        messages.success(request, f"Surprise Box '{box.nama_paket}' berhasil ditambahkan.")
        return redirect("food:restaurant_detail", restaurant_id=restaurant.id)

    return render(
        request,
        "food/surprise_box_form.html",
        {"form": form, "restaurant": restaurant, "title": f"Tambah Paket di {restaurant.nama}"},
    )


@login_required
def edit_surprise_box(request, box_id):
    box = get_object_or_404(SurpriseBox, id=box_id, is_active=True)
    if box.restaurant.owner != request.user and not request.user.is_staff:
        raise PermissionDenied("Kamu tidak memiliki izin mengedit paket ini.")

    form = SurpriseBoxForm(request.POST or None, instance=box)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Paket '{box.nama_paket}' berhasil diperbarui.")
        return redirect("food:restaurant_detail", restaurant_id=box.restaurant.id)

    return render(
        request,
        "food/surprise_box_form.html",
        {"form": form, "restaurant": box.restaurant, "box": box, "title": f"Edit Paket: {box.nama_paket}"},
    )


@login_required
@require_POST
def delete_surprise_box(request, box_id):
    box = get_object_or_404(SurpriseBox, id=box_id)
    if box.restaurant.owner != request.user and not request.user.is_staff:
        raise PermissionDenied("Kamu tidak memiliki izin menghapus paket ini.")

    restaurant_id = box.restaurant.id
    box.is_active = False
    box.save()
    messages.success(request, f"Paket '{box.nama_paket}' telah dihapus.")
    return redirect("food:restaurant_detail", restaurant_id=restaurant_id)


def api_restaurants(request):
    """API JSON sebaran restoran untuk modul peta / partner."""
    if Restaurant.objects.filter(is_active=True).exists():
        qs = Restaurant.objects.filter(is_active=True)
        results = [
            {
                "id": r.id,
                "nama": r.nama,
                "alamat": r.alamat,
                "lat": float(r.lat) if r.lat is not None else None,
                "lng": float(r.lng) if r.lng is not None else None,
                "jam_buka": r.jam_buka.strftime("%H:%M") if r.jam_buka else None,
                "jam_tutup": r.jam_tutup.strftime("%H:%M") if r.jam_tutup else None,
            }
            for r in qs
        ]
    else:
        data = _load_dummy_data()
        results = [r for r in data.get("restaurants", []) if r.get("is_active", True)]

    return JsonResponse({"restaurants": results})


def api_surprise_boxes(request):
    """API JSON paket surprise box."""
    if SurpriseBox.objects.filter(is_active=True).exists():
        qs = SurpriseBox.objects.filter(is_active=True, restaurant__is_active=True).select_related("restaurant")
        results = [
            {
                "id": b.id,
                "restaurant_id": b.restaurant.id,
                "restaurant_nama": b.restaurant.nama,
                "nama_paket": b.nama_paket,
                "harga_normal": float(b.harga_normal),
                "harga_diskon": float(b.harga_diskon),
                "diskon_persen": b.diskon_persen,
                "stok": b.stok,
                "pickup_start": b.pickup_start.isoformat() if b.pickup_start else None,
                "pickup_end": b.pickup_end.isoformat() if b.pickup_end else None,
            }
            for b in qs
        ]
    else:
        data = _load_dummy_data()
        results = [b for b in data.get("surprise_boxes", []) if b.get("is_active", True)]

    return JsonResponse({"surprise_boxes": results})
