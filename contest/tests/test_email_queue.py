from django.test import TestCase, override_settings
from django.utils import timezone
from django.core import mail
from django.core.management import call_command

from django.apps import apps

from contest.services import notify_students_on_test_completion


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@test.local',
    EMAIL_SEND_DELAY_SECONDS=0,
)
class ContestEmailQueueTests(TestCase):
    def setUp(self):
        CustomUser = apps.get_model('users', 'CustomUser')
        Tutor = apps.get_model('user_profile', 'Tutor')
        Category = apps.get_model('course', 'Category')
        Contest = apps.get_model('contest', 'Contest')
        Participant = apps.get_model('contest', 'Participant')

        # Users
        self.student_present = CustomUser.objects.create_user(email='present@example.com', username='present', password='pw', role='student')
        self.student_absent = CustomUser.objects.create_user(email='absent@example.com', username='absent', password='pw', role='student')
        self.tutor_user = CustomUser.objects.create_user(email='tutor@example.com', username='tutor', password='pw', role='tutor')
        self.tutor = Tutor.objects.create(user=self.tutor_user, display_name='Prof. Test')

        # Category and contest
        self.category = Category.objects.create(name='Unit Testing')
        now = timezone.now()
        self.contest = Contest.objects.create(
            tutor=self.tutor,
            category=self.category,
            name='Unit Test Contest',
            description='Test contest',
            total_questions=10,
            max_points=100,
            start_time=now - timezone.timedelta(days=1),
            end_time=now - timezone.timedelta(hours=1),
            status='scheduled',
            auto_email_results=True,
        )

        # Participants: one present, one absent (no submissions/time)
        self.p_present = Participant.objects.create(contest=self.contest, user=self.student_present, score=80, completed_at=timezone.now())
        self.p_absent = Participant.objects.create(contest=self.contest, user=self.student_absent, score=0)

    def test_queue_and_process_emails_present_and_absent(self):
        EmailLog = apps.get_model('contest', 'EmailLog')

        # Enqueue logs for all students of the contest
        notify_students_on_test_completion(self.contest.id)

        logs = EmailLog.objects.filter(contest=self.contest)
        self.assertEqual(logs.count(), 2, 'Should enqueue one EmailLog per student')
        self.assertTrue(all(not l.success for l in logs))

        # Process queue and send emails synchronously
        call_command('process_email_queue', limit=10, delay_seconds=0)

        logs = EmailLog.objects.filter(contest=self.contest)
        self.assertEqual(logs.filter(success=True).count(), 2, 'All emails should be marked success after processing')

        # Verify outbox contains two messages with correct subjects and context hints
        self.assertEqual(len(mail.outbox), 2)
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(all('Performance Summary' in s for s in subjects))

        # Find bodies per recipient
        bodies_by_to = {m.to[0]: m.body for m in mail.outbox}
        self.assertIn('present@example.com', bodies_by_to)
        self.assertIn('absent@example.com', bodies_by_to)

        present_body = bodies_by_to['present@example.com']
        absent_body = bodies_by_to['absent@example.com']

        self.assertIn('Attendance', present_body)
        self.assertIn('Present', present_body)
        self.assertIn('80', present_body)
        self.assertIn('Rank', present_body)
        # With two participants and scores 80 vs 0, ranks should be 1 and 2
        self.assertIn('1', present_body)

        self.assertIn('Attendance', absent_body)
        self.assertIn('Absent', absent_body)
        self.assertIn('0', absent_body)
        self.assertIn('2', absent_body)

        # Progress display (80% and 0%)
        self.assertIn('80%', present_body)
        self.assertIn('0%', absent_body)
