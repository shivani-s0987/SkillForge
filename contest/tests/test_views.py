from django.test import TestCase, override_settings
from django.utils import timezone
from django.apps import apps
from rest_framework.test import APIClient


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='no-reply@test.local',
)
class SendProgressReportsViewTests(TestCase):
    def setUp(self):
        CustomUser = apps.get_model('users', 'CustomUser')
        Tutor = apps.get_model('user_profile', 'Tutor')
        Category = apps.get_model('course', 'Category')
        Contest = apps.get_model('contest', 'Contest')

        self.client = APIClient()

        # Users
        self.student = CustomUser.objects.create_user(email='s@example.com', username='s', password='pw', role='student')
        self.tutor_user = CustomUser.objects.create_user(email='t@example.com', username='t', password='pw', role='tutor')
        self.tutor = Tutor.objects.create(user=self.tutor_user, display_name='Tutor')

        # Category and contests
        self.category = Category.objects.create(name='Unit')
        now = timezone.now()
        ContestModel = apps.get_model('contest', 'Contest')
        self.finished_contest = ContestModel.objects.create(
            tutor=self.tutor,
            category=self.category,
            name='Finished',
            description='d',
            total_questions=1,
            max_points=10,
            start_time=now - timezone.timedelta(days=1),
            end_time=now - timezone.timedelta(hours=1),
            status='finished',
        )
        self.ongoing_contest = ContestModel.objects.create(
            tutor=self.tutor,
            category=self.category,
            name='Ongoing',
            description='d',
            total_questions=1,
            max_points=10,
            start_time=now - timezone.timedelta(minutes=10),
            end_time=now + timezone.timedelta(minutes=10),
            status='ongoing',
        )

    def test_requires_authentication(self):
        resp = self.client.post(f'/contest/{self.finished_contest.id}/send-progress-reports/')
        self.assertEqual(resp.status_code, 401)

    def test_tutor_can_queue_for_finished_contest(self):
        self.client.force_authenticate(user=self.tutor_user)
        resp = self.client.post(f'/contest/{self.finished_contest.id}/send-progress-reports/')
        self.assertEqual(resp.status_code, 202)
        self.assertIn('contest_id', resp.data)

    def test_student_forbidden(self):
        self.client.force_authenticate(user=self.student)
        resp = self.client.post(f'/contest/{self.finished_contest.id}/send-progress-reports/')
        self.assertEqual(resp.status_code, 403)

    def test_contest_not_finished_returns_400(self):
        self.client.force_authenticate(user=self.tutor_user)
        resp = self.client.post(f'/contest/{self.ongoing_contest.id}/send-progress-reports/')
        self.assertEqual(resp.status_code, 400)
