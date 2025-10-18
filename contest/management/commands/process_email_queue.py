from django.core.management.base import BaseCommand
from django.utils import timezone
from django.apps import apps
from django.db import transaction
from django.conf import settings
from contest.services import send_contest_summary_email, build_contest_email_context
import time


class Command(BaseCommand):
    help = 'Process pending EmailLog entries and attempt to send due emails. Use for retries.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50, help='Max emails to process per run')
        parser.add_argument('--delay-seconds', type=int, default=None, help='Optional delay between sends to avoid throttling (defaults from settings or 3)')

    def handle(self, *args, **options):
        limit = options.get('limit') or 50
        EmailLog = apps.get_model('contest', 'EmailLog')
        Contest = apps.get_model('contest', 'Contest')
        User = apps.get_model('users', 'CustomUser')

        now = timezone.now()
        qs = EmailLog.objects.filter(success=False).filter(next_attempt_at__lte=now).order_by('next_attempt_at')[:limit]
        if not qs.exists():
            self.stdout.write('No pending emails to process.')
            return

        delay_seconds = options.get('delay_seconds')
        if delay_seconds is None:
            delay_seconds = getattr(settings, 'EMAIL_SEND_DELAY_SECONDS', 3)
        min_gap_per_recipient = getattr(settings, 'EMAIL_MIN_GAP_PER_RECIPIENT_SECONDS', 5)
        suppressed_recipients = set()
        last_send_ts_by_recipient = {}

        for log in qs:
            try:
                log.refresh_from_db()
                now = timezone.now()
                if log.success:
                    continue
                if log.next_attempt_at and log.next_attempt_at > now:
                    continue
                to_email_norm = (log.to_email or '').strip().lower()
                if to_email_norm in suppressed_recipients:
                    continue
                last_ts = last_send_ts_by_recipient.get(to_email_norm)
                if last_ts is not None:
                    elapsed = (timezone.now() - last_ts).total_seconds()
                    if elapsed < min_gap_per_recipient:
                        time.sleep(min_gap_per_recipient - elapsed)
                student = None
                if log.student_id:
                    student = User.objects.filter(id=log.student_id).first()
                if not student:
                    # try to match by email
                    student = User.objects.filter(email=log.to_email).first()
                if not student:
                    self.stdout.write(self.style.WARNING(f'No student found for EmailLog id={log.id} to={log.to_email}'))
                    continue

                contest = Contest.objects.filter(id=log.contest_id).first()
                if not contest:
                    self.stdout.write(self.style.WARNING(f'No contest found for EmailLog id={log.id} contest_id={log.contest_id}'))
                    continue

                # Build validated context for this student-contest pair
                ctx = build_contest_email_context(student, contest)

                # send email synchronously (no threading) to keep pacing predictable; reuse existing log
                send_contest_summary_email(
                    student,
                    contest,
                    marks=ctx['marks'],
                    rank=ctx['rank'],
                    attendance=ctx['attendance'],
                    avg_score=ctx['avg_score'],
                    tutor_name=ctx['tutor_name'],
                    progress_percent=ctx['progress_percent'],
                    top_score=ctx.get('max_scored'),
                    performance_summary=ctx.get('performance_summary'),
                    existing_log=log,
                    delay_seconds=0,
                    use_thread=False,
                )

                # refresh to inspect state
                log.refresh_from_db()
                if log.success:
                    self.stdout.write(self.style.SUCCESS(f'Sent email for EmailLog id={log.id} to={log.to_email}'))
                    last_send_ts_by_recipient[to_email_norm] = timezone.now()
                else:
                    # failure is already logged and next_attempt_at scheduled
                    self.stdout.write(self.style.WARNING(f'Email deferred/retry scheduled for EmailLog id={log.id}; error={log.error_text} next={log.next_attempt_at}'))
                    err = (log.error_text or '')
                    if ('ReceivingRate' in err) or ('receiving mail at a rate' in err):
                        suppressed_recipients.add(to_email_norm)
                if delay_seconds and delay_seconds > 0:
                    time.sleep(delay_seconds)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing EmailLog id={log.id}: {e}'))
