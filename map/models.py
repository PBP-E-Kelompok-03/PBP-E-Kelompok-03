from django.core.validators import URLValidator
from django.db import models


class RestaurantMapProfile(models.Model):
    """Map presentation data, without changing the food module's schema."""

    restaurant = models.OneToOneField(
        "food.Restaurant", on_delete=models.CASCADE, related_name="map_profile",
    )
    image_url = models.URLField(
        "URL foto restoran", max_length=2048, blank=True,
        validators=[URLValidator(schemes=["https"])],
        help_text="Tautan HTTPS langsung ke foto restoran. Kosongkan untuk menghapus foto.",
    )

    def __str__(self):
        return self.restaurant.nama
