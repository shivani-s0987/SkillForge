from django.db import models
from user_profile.models import Tutor
from users.models import CustomUser
from course.models import Category
from base.base_models import BaseModel
from django.utils.text import slugify
from django.utils import timezone

# Create your models here.

class Contest(BaseModel):
    """Model representing a contest, including its associated details and participants."""

    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('finished', 'Finished'),
    )
    AI_SUMMARY_STATUS = (
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    )

    tutor = models.ForeignKey(Tutor, on_delete=models.CASCADE, null=True, blank=True, related_name='contests')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='contests')
    slug = models.SlugField(max_length=250, unique=True, null=True)
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    total_questions = models.IntegerField(default=0)
    max_points = models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    difficulty_level = models.CharField(blank=True, max_length=50)
    time_limit = models.DurationField(null=True, blank=True, help_text="Time limit for contest participation (e.g., 00:10:00 for 10 minutes).")
    status = models.CharField(choices=STATUS_CHOICES, max_length=10, null=True)
    auto_email_results = models.BooleanField(default=True)
    participants = models.ManyToManyField(CustomUser, through='Participant', blank=True)
    ai_summary_status = models.CharField(max_length=20, choices=AI_SUMMARY_STATUS, default='pending')

    def save(self, *args, **kwargs):
        """Override save method to automatically generate a unique slug based on the contest name."""
        # detect previous status for change detection
        previous_status = None
        if self.pk:
            try:
                previous_status = Contest.objects.get(pk=self.pk).status
            except Exception:
                previous_status = None

        if not self.slug or Contest.objects.filter(pk=self.pk, name=self.name).exists() == False:
            base_slug = slugify(self.name)
            slug = base_slug
            num = 1
            while Contest.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{num}'
                num += 1
            self.slug = slug
        super().save(*args, **kwargs)

        # If status transitioned to 'finished', trigger notifications (non-blocking)
        try:
            new_status = self.status
            if previous_status != 'finished' and new_status == 'finished':
                # import here to avoid circular imports
                try:
                    from .services import notify_students_on_test_completion
                    # dispatch in a thread to avoid blocking
                    import threading
                    t = threading.Thread(target=notify_students_on_test_completion, args=(self.id,))
                    t.daemon = True
                    t.start()
                except Exception:
                    # if service not available, just log
                    import logging
                    logging.getLogger(__name__).exception('Failed to dispatch contest completion notifier for contest %s', self.id)
        except Exception:
            pass

    def __str__(self) -> str:
        """Return the contest name as a string representation."""
        return self.name



class EmailLog(BaseModel):
    """Stores records of outgoing contest summary emails for auditing."""

    student = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    contest = models.ForeignKey(Contest, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    to_email = models.CharField(max_length=254)
    subject = models.CharField(max_length=255)
    success = models.BooleanField(default=False)
    error_text = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    # retry fields
    attempt_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    max_attempts = models.IntegerField(default=5)

    class Meta:
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'

    def __str__(self) -> str:
        return f"EmailLog: {self.to_email} - {self.subject} - {'OK' if self.success else 'FAIL'}"


class Question(BaseModel):
    """Model representing a question associated with a contest."""

    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='questions', null=True)
    question_text = models.TextField()

    def __str__(self) -> str:
        """Return the question text as a string representation."""
        return self.question_text


class Option(BaseModel):
    """Model representing an option for a question in a contest."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options', null=True)
    option_text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)

    def __str__(self) -> str:
        """Return the option text as a string representation."""
        return self.option_text


class Participant(BaseModel):
    """Model representing a participant in a contest, including their score and time taken."""

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contest_participants', null=True)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='contest_participants', null=True)
    score = models.IntegerField(default=0)
    time_taken = models.DurationField(blank=True, null=True)
    completed_at = models.DateTimeField(null=True)

    def __str__(self) -> str:
        """Return a string representation of the participant's username and contest name."""
        return f"{self.user.username} - {self.contest.name}"


class Submission(BaseModel):
    """Model representing a submission made by a participant for a question in a contest."""

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='submissions', null=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='submissions', null=True)
    selected_option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self) -> str:
        """Return a string representation of the participant's username and the question text."""
        return f"{self.participant.user.username} - {self.question.question_text}"


class Leaderboard(BaseModel):
    """Model representing a leaderboard entry for a contest, including user scores and ranks."""

    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='leaderboards', null=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='leaderboards', null=True)
    score = models.IntegerField(default=0)
    rank = models.IntegerField(null=True)

    class Meta:
        unique_together = ('contest', 'user')

    def __str__(self) -> str:
        """Return a string representation of the user's username, contest name, and rank."""
        return f"{self.user.username} - {self.contest.name} - Rank: {self.rank}"


class SummarizedKeyNote(BaseModel):
    """Stores an AI-generated concise summary / key note for a question within a contest."""

    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='summaries', null=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='summaries', null=True)
    summary_text = models.TextField(blank=True, null=True)
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Summarized Key Note'
        verbose_name_plural = 'Summarized Key Notes'

    def __str__(self) -> str:
        return f"Summary for Question {self.question.id} in Contest {self.contest.id}"
