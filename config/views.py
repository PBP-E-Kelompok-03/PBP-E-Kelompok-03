from django.shortcuts import render
from food.models import Restaurant, SurpriseBox


def landing_page(request):
    boxes = SurpriseBox.objects.filter(is_active=True, restaurant__is_active=True)
    context = {
        "featured_boxes": list(boxes.select_related("restaurant")[:3]),
        "total_restaurants": Restaurant.objects.filter(is_active=True).count(),
        "total_boxes": boxes.count(),
    }
    return render(request, "landing.html", context)
