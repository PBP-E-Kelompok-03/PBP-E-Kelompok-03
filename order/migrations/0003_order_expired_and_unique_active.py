from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('food', '0001_initial'),
        ('order', '0002_order_surprise_box_fk'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('expired', 'Expired')], default='pending', max_length=10),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['pending', 'confirmed'])), fields=('pembeli', 'surprise_box'), name='uniq_active_order_per_box'),
        ),
    ]
