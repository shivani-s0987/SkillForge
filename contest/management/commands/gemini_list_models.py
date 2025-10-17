from django.core.management.base import BaseCommand
from contest.utils import discover_gemini_models


class Command(BaseCommand):
    help = 'List Gemini/Generative Language models available to the configured credentials'

    def handle(self, *args, **options):
        models = discover_gemini_models()
        if not models:
            self.stdout.write('No models discovered. Check GEMINI_API_KEY / GEMINI_BEARER_TOKEN and GEMINI_API_BASE settings.')
            return

        for root, m in models:
            self.stdout.write(f'Root: {root}')
            if isinstance(m, dict):
                name = m.get('name') or m.get('model') or m.get('id')
                self.stdout.write(f'  Model name: {name}')
                methods = m.get('supportedMethods') or m.get('availableMethods') or m.get('methods') or []
                if methods:
                    self.stdout.write(f'  Supported methods: {methods}')
                else:
                    self.stdout.write('  Supported methods: <unknown>')
            else:
                self.stdout.write(f'  Model object: {m}')
