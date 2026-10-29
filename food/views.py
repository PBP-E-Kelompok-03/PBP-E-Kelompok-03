from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from order.forms import MAX_PER_ORDER

from .api_client import FoodApiClient
from .forms import RestaurantForm, SurpriseBoxForm
from .models import Restaurant, SurpriseBox


def food_list(request):
    """
    Katalog Surprise Box murni dari model database ORM (SurpriseBox dan Restaurant).
    Mendukung pencarian nama paket atau nama restoran.
    """
    query = request.GET.get("q", "").strip()

    boxes_qs = SurpriseBox.objects.filter(
        is_active=True,
        restaurant__is_active=True,
    ).select_related("restaurant")

    if query:
        boxes_qs = boxes_qs.filter(
            Q(nama_paket__icontains=query) | Q(restaurant__nama__icontains=query)
        )

    surprise_boxes = list(boxes_qs)
    total_restaurants = len({b.restaurant_id for b in surprise_boxes})
    total_stock = sum(b.stok for b in surprise_boxes)

    context = {
        "surprise_boxes": surprise_boxes,
        "total_restaurants": total_restaurants,
        "total_stock": total_stock,
        "query": query,
        "is_from_db": True,
    }
    return render(request, "food/food_list.html", context)


def restaurant_detail(request, restaurant_id):
    """
    Detail restoran dan varian Surprise Box aktif murni dari model database ORM.
    """
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
    boxes = restaurant.surprise_boxes.filter(is_active=True)
    first_box = boxes.first()
    total_stock = sum(b.stok for b in boxes)

    return render(
        request,
        "food/restaurant_detail.html",
        {
            "restaurant": restaurant,
            "boxes": boxes,
            "first_box": first_box,
            "total_stock": total_stock,
            "max_per_order": MAX_PER_ORDER,
        },
    )


@login_required
def my_restaurants(request):
    restaurants = Restaurant.objects.filter(owner=request.user, is_active=True).prefetch_related("surprise_boxes")
    return render(request, "food/my_restaurants.html", {"restaurants": restaurants})


@login_required
def create_restaurant(request):
    if not (request.user.is_partner or request.user.is_staff):
        raise PermissionDenied("Hanya mitra restoran yang boleh menambah restoran.")
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
    """
    API JSON sebaran restoran untuk modul peta / partner menggunakan FoodApiClient.
    Mendukung caching TTL dan fallback yang aman.
    """
    client = FoodApiClient()
    query = request.GET.get("q", "").strip() or None
    results = client.get_restaurants(query=query)
    return JsonResponse({"restaurants": results})


def api_surprise_boxes(request):
    """
    API JSON paket surprise box menggunakan FoodApiClient.
    Mendukung caching TTL dan fallback yang aman.
    """
    client = FoodApiClient()
    query = request.GET.get("q", "").strip() or None
    restaurant_id_raw = request.GET.get("restaurant_id", "").strip()
    restaurant_id = int(restaurant_id_raw) if restaurant_id_raw.isdigit() else None
    results = client.get_surprise_boxes(restaurant_id=restaurant_id, query=query)
    return JsonResponse({"surprise_boxes": results})
