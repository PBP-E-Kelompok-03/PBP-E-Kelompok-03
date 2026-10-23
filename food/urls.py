from django.urls import path
from . import views

app_name = "food"

urlpatterns = [
    path("", views.food_list, name="list"),
    path("restaurant/<int:restaurant_id>/", views.restaurant_detail, name="restaurant_detail"),
    path("restaurant/create/", views.create_restaurant, name="create_restaurant"),
    path("restaurant/<int:restaurant_id>/edit/", views.edit_restaurant, name="edit_restaurant"),
    path("restaurant/<int:restaurant_id>/box/create/", views.create_surprise_box, name="create_surprise_box"),
    path("box/<int:box_id>/edit/", views.edit_surprise_box, name="edit_surprise_box"),
    path("box/<int:box_id>/delete/", views.delete_surprise_box, name="delete_surprise_box"),
    path("my-restaurants/", views.my_restaurants, name="my_restaurants"),
    path("api/restaurants/", views.api_restaurants, name="api_restaurants"),
    path("api/boxes/", views.api_surprise_boxes, name="api_surprise_boxes"),
]
