from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from food.models import Restaurant
from .forms import RestaurantPhotoForm
from .models import RestaurantMapProfile
from .services import restaurant_locations


@never_cache
@require_GET
def map_view(request):
    return render(request, "map/map.html", {"restaurants": restaurant_locations(request.user)})


@never_cache
@require_GET
def restaurants_data(request):
    return JsonResponse({"restaurants": restaurant_locations(request.user)})


@login_required
@require_http_methods(["GET", "POST"])
def restaurant_photo(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, pk=restaurant_id, is_active=True)
    if not (request.user.is_staff or restaurant.owner_id == request.user.pk):
        raise PermissionDenied("Hanya pemilik restoran yang boleh mengubah foto.")
    profile = RestaurantMapProfile.objects.filter(restaurant=restaurant).first()
    form = RestaurantPhotoForm(
        request.POST if request.method == "POST" else None,
        instance=profile or RestaurantMapProfile(restaurant=restaurant),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Foto restoran berhasil diperbarui.")
        return redirect("map:map")
    return render(request, "map/restaurant_photo.html", {"restaurant": restaurant, "form": form})
