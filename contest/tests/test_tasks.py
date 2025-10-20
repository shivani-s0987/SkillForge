from django.test import TestCase, override_settings
from django.utils import timezone
from django.core import mail
from django.apps import apps

from contest.tasks import queue_contest_progress_reports


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@test.local',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class ProgressReportTasksTests(TestCase):
    def setUp(self):
        CustomUser = apps.get_model('users', 'CustomUser')
        Tutor = apps.get_model('user_profile', 'Tutor')
        Category = apps.get_model('course', 'Category')
        Contest = apps.get_model('contest', 'Contest')
        Participant = apps.get_model('contest', 'Participant')

        # Users
        self.student1 = CustomUser.objects.create_user(email='student1@example.com', username='s1', password='pw', role='student')
        self.student2 = CustomUser.objects.create_user(email='student2@example.com', username='s2', password='pw', role='student')
        self.tutor_user = CustomUser.objects.create_user(email='tutor@example.com', username='tutor', password='pw', role='tutor')
        self.tutor = Tutor.objects.create(user=self.tutor_user, display_name='Prof. Progress')

        # Category & contest (finished)
        self.category = Category.objects.create(name='Email Tests')
        now = timezone.now()
        self.contest = Contest.objects.create(
            tutor=self.tutor,
            category=self.category,
            name='Email Queue Contest',
            description='Queue test',
            total_questions=5,
            max_points=50,
            start_time=now - timezone.timedelta(days=1),
            end_time=now - timezone.timedelta(hours=1),
            status='finished',
        )

        # Participants
        Participant.objects.create(contest=self.contest, user=self.student1, score=40, completed_at=timezone.now())
        Participant.objects.create(contest=self.contest, user=self.student2, score=10, completed_at=timezone.now())

        # Ensure both are also in the M2M (roster union covers both cases)
        self.contest.participants.add(self.student1)
        self.contest.participants.add(self.student2)

    def test_queue_and_send_reports(self):
        # Queue tasks (eager -> executes immediately)
        summary = queue_contest_progress_reports(self.contest.id, self.tutor_user.id)
        self.assertIn('queued_count', summary)
        self.assertEqual(summary['contest_id'], self.contest.id)
        self.assertEqual(summary['queued_count'], 2)

        # With eager and locmem backend, emails should be sent now
        self.assertEqual(len(mail.outbox), 2)
        subjects = [m.subject for m in mail.outbox]
        for s in subjects:
            self.assertIn('Performance Summary', s)

        # Bodies should include key context terms
        bodies = [m.body for m in mail.outbox]
        self.assertTrue(any('Attendance' in b for b in bodies))
        self.assertTrue(any('Progress' in b for b in bodies))
