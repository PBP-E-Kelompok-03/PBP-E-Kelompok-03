from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection

from food.models import Restaurant, SurpriseBox


class Command(BaseCommand):
    help = "Reset auto-increment sequences for PostgreSQL to prevent primary key collision"

    def handle(self, *args, **options):
        sequence_sql = connection.ops.sequence_reset_sql(no_style(), [Restaurant, SurpriseBox])
        if sequence_sql:
            with connection.cursor() as cursor:
                for sql in sequence_sql:
                    cursor.execute(sql)
            self.stdout.write(self.style.SUCCESS("Successfully reset PostgreSQL sequences for Restaurant and SurpriseBox."))
        else:
            self.stdout.write("No sequence reset needed for current database backend.")
