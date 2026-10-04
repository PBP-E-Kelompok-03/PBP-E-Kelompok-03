from django.core.management.base import BaseCommand

from order.views import expire_stale_orders


class Command(BaseCommand):
    help = "Tandai pesanan aktif yang melewati jendela pickup sebagai kedaluwarsa."

    def handle(self, *args, **options):
        count = expire_stale_orders()
        self.stdout.write(f"{count} pesanan kedaluwarsa")
