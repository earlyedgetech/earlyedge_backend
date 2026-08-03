import getpass

from admin_security.models import AdminMember, Role
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Creates a dashboard member with the Administrator role (first-time setup).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--full-name', required=True)
        parser.add_argument('--password', required=False)

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        full_name = options['full_name'].strip()
        password = options.get('password') or getpass.getpass('Password: ')

        if AdminMember.objects.filter(email=email).exists():
            raise CommandError(f'A dashboard member with email {email} already exists.')

        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('\n'.join(exc.messages))

        role, _ = Role.objects.get_or_create(slug='admin', defaults={'name': 'Administrator'})

        AdminMember.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            is_superuser=True,
        )

        self.stdout.write(self.style.SUCCESS(f'Dashboard admin "{email}" created with the Administrator role.'))
