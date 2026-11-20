from django.urls import path

from . import views

app_name = "map"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("restaurants/", views.restaurants_data, name="restaurants_data"),
    path("restaurant/<int:restaurant_id>/photo/", views.restaurant_photo, name="restaurant_photo"),
]
