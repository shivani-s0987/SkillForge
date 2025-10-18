from django.core.management.base import BaseCommand
from django.utils import timezone
from django.apps import apps
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Mark contests whose end_time has passed as finished and enqueue result emails. Optionally process the email queue.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50, help='Max contests to process per run')
        parser.add_argument('--process', action='store_true', help='After enqueuing, process the email queue in this run')
        parser.add_argument('--process-limit', type=int, default=200, help='Max emails to process if --process is used')
        parser.add_argument('--delay-seconds', type=int, default=None, help='Optional delay between sends when processing')
        parser.add_argument('--dry-run', action='store_true', help='Only print actions without making changes')

    def handle(self, *args, **options):
        Contest = apps.get_model('contest', 'Contest')

        now = timezone.now()
        qs = (
            Contest.objects
            .filter(end_time__isnull=False, end_time__lte=now)
            .exclude(status='finished')
            .order_by('end_time')
        )
        limit = options.get('limit') or 50
        dry_run = bool(options.get('dry_run'))

        contests = list(qs[:limit])
        if not contests:
            self.stdout.write('No ended contests to process.')
            return

        self.stdout.write(f'Found {len(contests)} ended contest(s) to finish and enqueue.')

        processed = 0
        for c in contests:
            try:
                if dry_run:
                    self.stdout.write(self.style.NOTICE(f'[DRY-RUN] Would mark contest id={c.id} name="{c.name}" as finished and enqueue emails'))
                    continue
                prev = c.status
                c.status = 'finished'
                # This save triggers notify_students_on_test_completion via Contest.save()
                c.save(update_fields=['status'])
                processed += 1
                self.stdout.write(self.style.SUCCESS(f'Marked contest id={c.id} ({prev} -> finished); enqueued notifications'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed processing contest id={getattr(c, "id", None)}: {e}'))

        if options.get('process') and not dry_run:
            plimit = options.get('process_limit') or 200
            delay = options.get('delay_seconds')
            self.stdout.write(self.style.NOTICE(f'Processing email queue now (limit={plimit}, delay={delay})'))
            # Delegate to existing queue processor
            if delay is None:
                call_command('process_email_queue', limit=plimit)
            else:
                call_command('process_email_queue', limit=plimit, delay_seconds=delay)

        self.stdout.write(self.style.SUCCESS(f'Done. Contests updated: {processed}'))
