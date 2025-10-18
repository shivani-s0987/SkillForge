from django.core.management.base import BaseCommand, CommandError
from contest.models import EmailLog, Contest
from contest.services import notify_students_on_test_completion, send_contest_summary_email, build_contest_email_context
from django.apps import apps


class Command(BaseCommand):
    help = 'Send contest summary emails for a contest or resend failed emails for a contest'

    def add_arguments(self, parser):
        parser.add_argument('contest_id', type=int, help='ID of the contest')
        parser.add_argument('--resend-failed', action='store_true', help='Only resend failed EmailLog entries for this contest')

    def handle(self, *args, **options):
        contest_id = options['contest_id']
        resend_failed = options['resend_failed']

        try:
            contest = Contest.objects.get(id=contest_id)
        except Contest.DoesNotExist:
            raise CommandError(f'Contest with id={contest_id} not found')

        if resend_failed:
            self.stdout.write(self.style.NOTICE(f'Resending failed emails for contest {contest_id}'))
            failed_logs = EmailLog.objects.filter(contest_id=contest_id, success=False)
            if not failed_logs.exists():
                self.stdout.write('No failed logs found.')
                return

            Participant = apps.get_model('contest', 'Participant')
            Leaderboard = apps.get_model('contest', 'Leaderboard')

            lb_map = {lb.user_id: lb.rank for lb in Leaderboard.objects.filter(contest=contest)}

            for log in failed_logs:
                student = None
                if log.student_id:
                    try:
                        student = apps.get_model('users', 'CustomUser').objects.get(id=log.student_id)
                    except Exception:
                        student = None

                if not student:
                    self.stdout.write(self.style.WARNING(f'Cannot find student for EmailLog id={log.id}, to={log.to_email}'))
                    continue

                p = Participant.objects.filter(contest=contest, user=student).first()
                attendance = 'Present' if p else 'Absent'
                marks = p.score if p else 0
                rank = lb_map.get(student.id)

                ctx = build_contest_email_context(student, contest)
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
                )
                self.stdout.write(self.style.SUCCESS(f'Redispatched for student {student.id}'))

            self.stdout.write(self.style.SUCCESS('Resend complete.'))
        else:
            self.stdout.write(self.style.NOTICE(f'Triggering notify_students_on_test_completion for contest {contest_id}'))
            notify_students_on_test_completion(contest_id)
            self.stdout.write(self.style.SUCCESS('Dispatch complete.'))
