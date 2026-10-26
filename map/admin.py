from django.contrib import admin

from .models import RestaurantMapProfile


@admin.register(RestaurantMapProfile)
class RestaurantMapProfileAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "image_url")
    search_fields = ("restaurant__nama",)
    autocomplete_fields = ("restaurant",)
