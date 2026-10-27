import math
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Min, Q, Sum
from django.templatetags.static import static
from django.urls import reverse

from food.models import Restaurant


def restaurant_locations(user=None):
    """Return database-backed stock and prices of active surprise boxes."""
    active = Q(surprise_boxes__is_active=True)
    available = active & Q(surprise_boxes__stok__gt=0)
    restaurants = (
        Restaurant.objects.filter(is_active=True).select_related("map_profile")
        .annotate(
            total_stock=Sum("surprise_boxes__stok", filter=active, default=0),
            available_stock=Sum("surprise_boxes__stok", filter=available, default=0),
            min_discount_price=Min("surprise_boxes__harga_diskon", filter=available),
        )
    )
    placeholder = static("map/restaurant-placeholder.svg")
    locations = []
    for restaurant in restaurants:
        try:
            lat, lng = float(restaurant.lat), float(restaurant.lng)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lng)
                and -90 <= lat <= 90 and -180 <= lng <= 180):
            continue

        profile = getattr(restaurant, "map_profile", None)
        image_url = profile.image_url if profile else ""
        if image_url:
            try:
                URLValidator(schemes=["https"])(image_url)
            except ValidationError:
                image_url = ""
        if restaurant.available_stock:
            status = "available"
            stock_label = f"{restaurant.available_stock} paket tersedia"
        else:
            status, stock_label = "sold_out", "Stok habis"

        can_edit_photo = bool(user and user.is_authenticated and (
            user.is_staff or restaurant.owner_id == user.pk
        ))
        # Let Google Maps choose/ask for the origin, even when geolocation is denied.
        # Decimal fixed-point formatting avoids locale commas and scientific notation.
        directions_url = "https://www.google.com/maps/dir/?" + urlencode({
            "api": 1,
            "destination": f"{restaurant.lat:f},{restaurant.lng:f}",
            "dir_action": "navigate",
        })
        locations.append({
            "id": restaurant.pk, "nama": restaurant.nama, "alamat": restaurant.alamat,
            "lat": lat, "lng": lng,
            "jam_buka": restaurant.jam_buka.strftime("%H:%M") if restaurant.jam_buka else None,
            "jam_tutup": restaurant.jam_tutup.strftime("%H:%M") if restaurant.jam_tutup else None,
            "total_stock": restaurant.total_stock,
            "available_stock": restaurant.available_stock,
            "has_stock": restaurant.total_stock > 0,
            "is_available": restaurant.available_stock > 0,
            "stock_status": status, "stock_label": stock_label,
            "min_discount_price": (
                str(restaurant.min_discount_price) if restaurant.min_discount_price is not None else None
            ),
            "image_url": image_url or placeholder, "has_image": bool(image_url),
            "directions_url": directions_url,
            "detail_url": reverse("food:restaurant_detail", args=[restaurant.pk]),
            "photo_edit_url": reverse("map:restaurant_photo", args=[restaurant.pk]) if can_edit_photo else None,
        })
    return locations
