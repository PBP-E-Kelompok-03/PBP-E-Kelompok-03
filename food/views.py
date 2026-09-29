import json
from pathlib import Path
from django.conf import settings
from django.shortcuts import render


def food_list(request):
    fixture_path = Path(settings.BASE_DIR) / "fixtures" / "dummy_data.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    restaurants_by_id = {
        r["id"]: r for r in data.get("restaurants", []) if r.get("is_active", True)
    }

    query = request.GET.get("q", "").strip().lower()
    surprise_boxes = []

    for box in data.get("surprise_boxes", []):
        if not box.get("is_active", True):
            continue
        restaurant = restaurants_by_id.get(box.get("restaurant_id"))
        if not restaurant:
            continue

        if query and query not in box["nama_paket"].lower() and query not in restaurant["nama"].lower():
            continue

        harga_normal = box.get("harga_normal", 0)
        harga_diskon = box.get("harga_diskon", 0)
        diskon_persen = (
            round((harga_normal - harga_diskon) / harga_normal * 100)
            if harga_normal > 0
            else 0
        )

        surprise_boxes.append({
            **box,
            "restaurant": restaurant,
            "diskon_persen": diskon_persen,
        })

    context = {
        "surprise_boxes": surprise_boxes,
        "total_restaurants": len(restaurants_by_id),
        "query": request.GET.get("q", "").strip(),
    }
    return render(request, "food/food_list.html", context)

