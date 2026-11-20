import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("food", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="RestaurantMapProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image_url", models.URLField(
                    blank=True, max_length=2048,
                    validators=[django.core.validators.URLValidator(schemes=["https"])],
                    verbose_name="URL foto restoran",
                    help_text="Tautan HTTPS langsung ke foto restoran. Kosongkan untuk menghapus foto.",
                )),
                ("restaurant", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="map_profile", to="food.restaurant",
                )),
            ],
        ),
    ]
