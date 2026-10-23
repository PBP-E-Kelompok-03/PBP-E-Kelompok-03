import math

from django.shortcuts import render
from django.urls import reverse

from food.models import Restaurant
from food.views import _load_dummy_data


def map_view(request):
    """Use the same restaurant source as the food module."""
    restaurants = list(Restaurant.objects.filter(is_active=True).values(
        "id", "nama", "alamat", "lat", "lng", "jam_buka", "jam_tutup"
    ))
    if not restaurants:
        restaurants = [
            restaurant.copy()
            for restaurant in _load_dummy_data().get("restaurants", [])
            if restaurant.get("is_active", True)
        ]

    locations = []
    for restaurant in restaurants:
        try:
            lat, lng = float(restaurant["lat"]), float(restaurant["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lng)
                and -90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        restaurant["lat"], restaurant["lng"] = lat, lng
        for field in ("jam_buka", "jam_tutup"):
            value = restaurant.get(field)
            restaurant[field] = value.strftime("%H:%M") if hasattr(value, "strftime") else value
        restaurant["detail_url"] = reverse(
            "food:restaurant_detail", args=[restaurant["id"]]
        )
        locations.append(restaurant)

    return render(request, "map/map.html", {"restaurants": locations})
