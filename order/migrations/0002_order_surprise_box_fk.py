import django.db.models.deletion
from django.db import migrations, models


def drop_orphan_orders(apps, schema_editor):
    Order = apps.get_model("order", "Order")
    SurpriseBox = apps.get_model("food", "SurpriseBox")
    valid = SurpriseBox.objects.values_list("id", flat=True)
    Order.objects.exclude(surprise_box_id__in=valid).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("food", "0001_initial"),
        ("order", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(drop_orphan_orders, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="order",
            old_name="surprise_box_id",
            new_name="surprise_box",
        ),
        migrations.AlterField(
            model_name="order",
            name="surprise_box",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="food.surprisebox",
            ),
        ),
    ]
