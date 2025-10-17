from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from contest.models import Contest
from contest.tasks import generate_summaries_for_contest


class Command(BaseCommand):
    help = 'Regenerate AI summaries for a contest or for all contests. Usage: regenerate_summaries --contest-id=1 or --all'

    def add_arguments(self, parser):
        parser.add_argument('--contest-id', type=int, help='ID of the contest to regenerate summaries for')
        parser.add_argument('--all', action='store_true', help='Regenerate summaries for all contests')

    def handle(self, *args, **options):
        contest_id = options.get('contest_id')
        do_all = options.get('all')

        if not contest_id and not do_all:
            raise CommandError('Must provide --contest-id or --all')

        if do_all:
            contests = Contest.objects.all()
        else:
            try:
                contests = [Contest.objects.get(id=contest_id)]
            except Contest.DoesNotExist:
                raise CommandError(f'Contest with id {contest_id} does not exist')

        self.stdout.write(self.style.NOTICE(f'Starting regeneration for {len(contests)} contest(s)'))

        for c in contests:
            self.stdout.write(f'Processing contest id={c.id} name={c.name}')
            try:
                # Call generation synchronously (task returns nothing) — this will update ai_summary_status
                generate_summaries_for_contest(c.id)
                self.stdout.write(self.style.SUCCESS(f'Finished contest {c.id}'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed contest {c.id}: {e}'))
