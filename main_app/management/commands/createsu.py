from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

class Command(BaseCommand):

    def handle(self, *args, **options):
        if not User.objects.filter(username="warmline_admin").exists():
            User.objects.create_superuser("warmline_admin", "warmlineadmin@admin.com", "qweqweqwe")
            self.stdout.write(self.style.SUCCESS('Successfully created new super user'))
