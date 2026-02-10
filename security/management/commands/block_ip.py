from django.core.management.base import BaseCommand
from security.models import BlockedIP


class Command(BaseCommand):
    help = 'Block a specific IP address'

    def add_arguments(self, parser):
        parser.add_argument('ip_address',
                            type=str,
                            help='The IP address to block')

    def handle(self, *args, **kwargs):
        ip_address = kwargs['ip_address']

        # If the IP is already blocked, do nothing, else block it by creating a BlockedIP entry
        blocked_ip, created = BlockedIP.objects.get_or_create(ip_address=ip_address)

        if created:
            self.stdout.write(self.style.SUCCESS(f'Successfully blocked IP address: {ip_address}'))
        else:
            self.stdout.write(self.style.WARNING(f'IP address {ip_address} is already blocked'))