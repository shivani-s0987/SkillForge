from celery import shared_task
from .models import Contest
from django.utils.timezone import now
from django.core.cache import cache
from django.apps import apps
import logging
from django.core.management import call_command
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def update_contest_status_task():
    current_time = now()

    # Fetch relevant contests based on their start and end times
    contests = Contest.objects.all().exclude(status='finished')

    for contest in contests:
        updated_status = None

        if contest.start_time <= current_time <= contest.end_time:
            if contest.status != 'ongoing':
                updated_status = 'ongoing'
        elif current_time > contest.end_time:
            if contest.status != 'finished':
                updated_status = 'finished'
        else:  # current_time < contest.start_time
            if contest.status != 'scheduled':
                updated_status = 'scheduled'

        # Update contest status if it has changed
        if updated_status:
            contest.status = updated_status
            contest.save()

    # Clear the cache only once after processing all contests
    cache.clear()


@shared_task
def generate_summaries_for_contest(contest_id, triggered_by_user_id=None):
    """Celery task to call the SummarizedKeyNote generator view logic.

    This task tries to import the SummarizedKeyNote generation logic from views to avoid duplication.
    """
    try:
        Contest = apps.get_model('contest', 'Contest')
        SummarizedKeyNote = apps.get_model('contest', 'SummarizedKeyNote')
        from .views import call_summarizer
        contest = Contest.objects.get(id=contest_id)
        # Gather notes similar to the view
        notes_texts = []
        if contest.category and contest.category.courses.exists():
            first_course = contest.category.courses.first()
            for module in first_course.modules.all():
                try:
                    if module.notes and hasattr(module.notes, 'open'):
                        with module.notes.open('r', encoding='utf-8', errors='ignore') as f:
                            notes_texts.append(f.read())
                except Exception:
                    continue

        # mark generating
        try:
            contest.ai_summary_status = 'generating'
            contest.save()
        except Exception:
            pass

        from .utils import summarize_question_obj
        for q in contest.questions.all():
            summary_obj, created = SummarizedKeyNote.objects.get_or_create(contest=contest, question=q)
            # Always (re)generate and overwrite using the robust summarizer
            generated = summarize_question_obj(q, notes_texts)
            summary_obj.summary_text = generated
            summary_obj.save()

        # mark ready
        try:
            contest.ai_summary_status = 'ready'
            contest.save()
        except Exception:
            pass
    except Exception as e:
        logger.exception('Failed to generate summaries for contest %s: %s', contest_id, e)
        try:
            contest.ai_summary_status = 'failed'
            contest.save()
        except Exception:
            pass


@shared_task
def regenerate_summaries_command(triggered_by_user_id=None):
    """Run the `regenerate_summaries` management command from a Celery worker.

    This allows the web request to queue a background job instead of blocking.
    """
    try:
        logger.info('Celery task: calling regenerate_summaries management command')
        # call the management command to regenerate summaries for all contests
        # pass all=True to match the command flag
        call_command('regenerate_summaries', all=True)
        logger.info('Celery task: regenerate_summaries completed')
    except Exception as e:
        logger.exception('Celery task regenerate_summaries failed: %s', e)


# ------------------------------
# Progress report email tasks
# ------------------------------

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=3600, retry_jitter=True, max_retries=5)
def send_student_report_email(self, to_email: str, subject: str, html_body: str, contest_id: int = None, student_id: int = None):
    """Send a single student's progress report email.

    Uses HTML and text alternative, validates email, and logs outcomes. Retries on failure with backoff.
    """
    try:
        if not to_email:
            logger.warning('Skipping send: empty to_email for student=%s contest=%s', student_id, contest_id)
            return False
        try:
            validate_email(to_email)
        except ValidationError:
            logger.warning('Skipping send: invalid email %s for student=%s contest=%s', to_email, student_id, contest_id)
            return False

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_HOST_USER', 'no-reply@skillforge.local'))
        text_body = html_body
        try:
            # If html contains tags, derive a basic text version
            from django.utils.html import strip_tags
            text_body = strip_tags(html_body)
        except Exception:
            pass

        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info('Sent progress report to=%s student=%s contest=%s', to_email, student_id, contest_id)
        return True
    except Exception as e:
        logger.exception('Failed sending progress report to=%s student=%s contest=%s: %s', to_email, student_id, contest_id, e)
        # Let autoretry_for handle retry
        raise


@shared_task
def queue_contest_progress_reports(contest_id: int, initiated_by_user_id: int = None) -> dict:
    """Queue per-student progress report emails for a contest with 10s spacing between each send.

    The scheduling is done via Celery apply_async(countdown=i*10) to avoid blocking workers.
    Returns a summary dict: {queued_count, contest_id}.
    """
    try:
        Contest = apps.get_model('contest', 'Contest')
        CustomUser = apps.get_model('users', 'CustomUser')

        contest = Contest.objects.select_related('tutor').filter(id=contest_id).first()
        if not contest:
            logger.warning('queue_contest_progress_reports: contest %s not found', contest_id)
            return {'queued_count': 0, 'contest_id': contest_id}

        # Only for finished contests (status or time-based)
        is_finished = False
        try:
            is_finished = (contest.status == 'finished') or (contest.end_time and contest.end_time <= timezone.now())
        except Exception:
            is_finished = False
        if not is_finished:
            logger.info('Contest %s not finished; skipping queue', contest_id)
            return {'queued_count': 0, 'contest_id': contest_id}

        # Build roster and leader data
        from .services import build_contest_email_context, get_contest_roster_user_ids
        user_ids = list(get_contest_roster_user_ids(contest))

        # Precompute any shared aggregates for template
        subject = f"\U0001F4CA {contest.name} – Performance Summary"

        # Queue each email with 10s spacing
        countdown_gap = 10
        # TODO: Integrate provider-side rate limiting (per-minute caps) if student volume is high.
        count = 0
        for idx, uid in enumerate(user_ids):
            try:
                student = CustomUser.objects.filter(id=uid).first()
                if not student or not getattr(student, 'email', None):
                    continue

                ctx = build_contest_email_context(student, contest)
                # Build template context
                try:
                    tutor_name = ctx.get('tutor_name')
                except Exception:
                    tutor_name = None

                context = {
                    'student': student,
                    'contest': contest,
                    'marks': ctx.get('marks'),
                    'rank': ctx.get('rank'),
                    'attendance': ctx.get('attendance'),
                    'avg_score': ctx.get('avg_score'),
                    'tutor_name': tutor_name,
                    'date_conducted': contest.start_time or contest.end_time or getattr(contest, 'created_at', timezone.now()),
                    'max_marks': contest.max_points or 0,
                    'progress_percent': ctx.get('progress_percent'),
                    'top_score': ctx.get('max_scored'),
                    'performance_summary': ctx.get('performance_summary'),
                    'now': timezone.now(),
                    'request': type('req', (), {'site_url': getattr(settings, 'SITE_URL', None)})(),
                }
                html = render_to_string('contest/email/contest_report.html', context)

                send_student_report_email.apply_async(
                    args=[student.email, subject, html, contest.id, student.id],
                    countdown=idx * countdown_gap,
                )
                count += 1
            except Exception:
                logger.exception('Failed to schedule email for contest=%s student=%s', contest_id, uid)
                continue

        logger.info('Queued %s progress report emails for contest=%s (gap=%ss)', count, contest_id, countdown_gap)
        return {'queued_count': count, 'contest_id': contest_id, 'spacing_seconds': countdown_gap}
    except Exception as e:
        logger.exception('queue_contest_progress_reports failed for contest %s: %s', contest_id, e)
        return {'queued_count': 0, 'contest_id': contest_id, 'error': str(e)}
