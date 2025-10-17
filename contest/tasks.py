from celery import shared_task
from .models import Contest
from django.utils.timezone import now
from django.core.cache import cache
from django.apps import apps
import logging
from django.core.management import call_command

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
