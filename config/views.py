from django.shortcuts import render
from food.models import Restaurant, SurpriseBox


def landing_page(request):
    try:
        featured_boxes = list(
            SurpriseBox.objects.filter(is_active=True, restaurant__is_active=True)
            .select_related("restaurant")[:3]
        )
        total_restaurants = Restaurant.objects.filter(is_active=True).count()
        total_boxes = SurpriseBox.objects.filter(is_active=True).count()
    except Exception:
        featured_boxes = []
        total_restaurants = 50
        total_boxes = 150

    context = {
        "featured_boxes": featured_boxes,
        "total_restaurants": total_restaurants or 50,
        "total_boxes": total_boxes or 150,
    }
    return render(request, "landing.html", context)
