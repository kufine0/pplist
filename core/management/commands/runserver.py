"""
Custom runserver command that reads port from database config.
"""
import os
from django.core.management.commands.runserver import Command as BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Run server with port configured in admin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            type=int,
            help='Port to run the server on. Overrides database config.',
        )
        parser.add_argument(
            '--addrport',
            help='Port or port:IP to run the server on. Overrides database config.',
        )
        super().add_arguments(parser)

    def get_port(self):
        """Get port from admin config, environment, or default"""
        # 1. Check command line argument
        if self._port:
            return self._port

        # 2. Check environment variable
        env_port = os.environ.get('SERVER_PORT')
        if env_port:
            try:
                return int(env_port)
            except ValueError:
                pass

        # 3. Try to get from database SystemConfig
        try:
            from core.models import SystemConfig
            config = SystemConfig.objects.filter(key='server_port').first()
            if config:
                return int(config.value)
        except Exception:
            pass

        # 4. Fall back to settings default
        return getattr(settings, 'SERVER_PORT', 8000)

    def handle(self, *args, **options):
        self._port = options.get('port')

        # If addrport is provided, parse it
        addrport = options.get('addrport')
        if addrport:
            if ':' in addrport:
                options['addrport'] = addrport
            else:
                try:
                    port = int(addrport)
                    options['addrport'] = f'127.0.0.1:{port}'
                except ValueError:
                    pass
        else:
            port = self.get_port()
            addr = getattr(settings, 'RUNSERVER addr', '127.0.0.1')
            options['addrport'] = f'{addr}:{port}'
            self.stdout.write(f'Using port from config: {port}')

        super().handle(*args, **options)
