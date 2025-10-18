import logging
from concurrent.futures import ThreadPoolExecutor
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.apps import apps
from django.utils import timezone
import json
import smtplib
import time
import random

try:
    import requests
except Exception:
    requests = None

logger = logging.getLogger(__name__)

# limit threads to avoid overload
executor = ThreadPoolExecutor(max_workers=5)


def send_contest_summary_email(
    student,
    contest,
    marks=0,
    rank=None,
    attendance='Absent',
    avg_score=None,
    tutor_name=None,
    progress_percent=None,
    top_score=None,
    performance_summary=None,
    existing_log=None,
    delay_seconds=0,
    use_thread=None,
):
    """Send a single contest summary email to a student.

    Builds both text and HTML content. Can run synchronously or via threadpool.
    If an EmailLog instance is provided via existing_log, it will be reused and updated
    by the send routine instead of creating a new log entry.
    """
    try:
        subject = f"📊 {contest.name} – Performance Summary"
        from_email = getattr(
            settings,
            'DEFAULT_FROM_EMAIL',
            settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else 'no-reply@skillforge.com'
        )
        to = [student.email]

        # compute progress if not provided
        max_marks = contest.max_points or 0
        if progress_percent is None:
            try:
                progress_percent = round(((marks or 0) / max_marks) * 100, 2) if max_marks else 0
            except Exception:
                progress_percent = 0

        context = {
            'student': student,
            'contest': contest,
            'marks': marks,
            'rank': rank,
            'attendance': attendance,
            'avg_score': avg_score,
            'tutor_name': tutor_name,
            'date_conducted': contest.start_time or contest.end_time or contest.created_at,
            'max_marks': max_marks,
            'progress_percent': progress_percent,
            'top_score': top_score,
            'performance_summary': performance_summary,
            'now': timezone.now(),
            'brand_color': '#6B21A8',  # purple accent
        }

        html_content = render_to_string('contest/email/contest_report.html', context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(subject, text_content, from_email, to)
        email.attach_alternative(html_content, "text/html")

        log = None
        if existing_log is not None:
            log = existing_log
        else:
            try:
                EmailLog = apps.get_model('contest', 'EmailLog')
                existing_unsent = EmailLog.objects.filter(
                    student_id=student.id,
                    contest_id=contest.id,
                    subject=subject,
                    success=False,
                ).order_by('id').first()
                if existing_unsent:
                    log = existing_unsent
                else:
                    cooldown_minutes = getattr(settings, 'EMAIL_RECIPIENT_COOLDOWN_MINUTES', 30)
                    recent_success = EmailLog.objects.filter(to_email__iexact=(student.email or ''), success=True).order_by('-last_attempt_at').first()
                    next_attempt_at = None
                    from datetime import timedelta
                    if recent_success and recent_success.last_attempt_at:
                        delta = timezone.now() - recent_success.last_attempt_at
                        if delta.total_seconds() < (cooldown_minutes * 60):
                            next_attempt_at = recent_success.last_attempt_at + timedelta(minutes=cooldown_minutes)
                    if next_attempt_at is None:
                        active_block = EmailLog.objects.filter(
                            to_email__iexact=(student.email or ''),
                            success=False,
                            next_attempt_at__gt=timezone.now(),
                        ).order_by('-next_attempt_at').values_list('next_attempt_at', flat=True).first()
                        if active_block:
                            next_attempt_at = active_block

                    log = EmailLog.objects.create(
                        student_id=student.id,
                        contest_id=contest.id,
                        to_email=student.email or '',
                        subject=subject,
                        success=False,
                        next_attempt_at=next_attempt_at,
                    )
            except Exception:
                log = None

        # If log scheduled for future (cooldown), do not send now; process_email_queue will pick it later
        if log and log.next_attempt_at and (log.next_attempt_at > timezone.now()):
            logger.info('Scheduled email for student=%s contest=%s after cooldown until %s', student.id, contest.id, log.next_attempt_at)
            return None

        if delay_seconds and delay_seconds > 0 and existing_log is None:
            time.sleep(delay_seconds)

        # decide whether to send synchronously
        if use_thread is None:
            use_thread = getattr(settings, 'EMAIL_SEND_USE_THREADPOOL', True)

        if use_thread:
            future = executor.submit(_send_email_safe, email, student.id, contest.id, log.id if log else None)
            return future
        else:
            _send_email_safe(email, student.id, contest.id, log.id if log else None)
            return True
    except Exception as e:
        logger.exception('Failed to enqueue email for student %s contest %s: %s', getattr(student, 'id', None), getattr(contest, 'id', None), e)
        return None


def _send_email_safe(email_message: EmailMultiAlternatives, student_id=None, contest_id=None, log_id=None):
    try:
        result = email_message.send(fail_silently=False)
        logger.info('Sent contest summary email to student=%s contest=%s', student_id, contest_id)
        # Persist EmailLog success or update existing
        try:
            EmailLog = apps.get_model('contest', 'EmailLog')
            if log_id:
                el = EmailLog.objects.filter(id=log_id).first()
                if el:
                    el.success = True
                    el.attempt_count = (el.attempt_count or 0) + 1
                    el.last_attempt_at = timezone.now()
                    el.next_attempt_at = None
                    el.error_text = None
                    el.save(update_fields=['success', 'attempt_count', 'last_attempt_at', 'next_attempt_at', 'error_text'])
            else:
                EmailLog.objects.create(student_id=student_id, contest_id=contest_id, to_email=','.join(email_message.to or []), subject=email_message.subject, success=True, attempt_count=1)
        except Exception:
            logger.exception('Failed to write EmailLog for success student=%s contest=%s', student_id, contest_id)
        return bool(result)
    except Exception as e:
        logger.exception('Error sending contest email student=%s contest=%s: %s', student_id, contest_id, e)
        # If it's an SMTP temporary recipient refusal and SendGrid API is configured, try SendGrid as a fallback
        sendgrid_key = getattr(settings, 'SENDGRID_API_KEY', None)
        tried_sendgrid = False
        if sendgrid_key and requests is not None:
            try:
                # build payload
                tried_sendgrid = True
                to_emails = email_message.to or []
                html = None
                for alt in getattr(email_message, 'alternatives', []) or []:
                    if alt and alt[1] == 'text/html':
                        html = alt[0]
                        break
                if html is None:
                    html = strip_tags(email_message.body)

                payload = {
                    "personalizations": [{"to": [{"email": e} for e in to_emails]}],
                    "from": {"email": getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)},
                    "subject": email_message.subject,
                    "content": [
                        {"type": "text/plain", "value": strip_tags(html)},
                        {"type": "text/html", "value": html},
                    ],
                }
                headers = {
                    'Authorization': f'Bearer {sendgrid_key}',
                    'Content-Type': 'application/json'
                }
                r = requests.post('https://api.sendgrid.com/v3/mail/send', headers=headers, data=json.dumps(payload), timeout=15)
                if r.status_code in (200, 202):
                    # treat as success
                    logger.info('SendGrid accepted email for student=%s contest=%s', student_id, contest_id)
                    try:
                        EmailLog = apps.get_model('contest', 'EmailLog')
                        if log_id:
                            el = EmailLog.objects.filter(id=log_id).first()
                            if el:
                                el.success = True
                                el.attempt_count = (el.attempt_count or 0) + 1
                                el.last_attempt_at = timezone.now()
                                el.next_attempt_at = None
                                el.error_text = None
                                el.save(update_fields=['success', 'attempt_count', 'last_attempt_at', 'next_attempt_at', 'error_text'])
                        else:
                            EmailLog.objects.create(student_id=student_id, contest_id=contest_id, to_email=','.join(email_message.to or []), subject=email_message.subject, success=True, attempt_count=1)
                    except Exception:
                        logger.exception('Failed to write EmailLog after SendGrid success for %s', student_id)
                    return True
                else:
                    logger.warning('SendGrid send returned status %s: %s', r.status_code, getattr(r, 'text', ''))
            except Exception:
                logger.exception('SendGrid fallback failed for student=%s contest=%s', student_id, contest_id)
        try:
            EmailLog = apps.get_model('contest', 'EmailLog')
            if log_id:
                el = EmailLog.objects.filter(id=log_id).first()
                if el:
                    el.attempt_count = (el.attempt_count or 0) + 1
                    el.last_attempt_at = timezone.now()
                    el.error_text = str(e)
                    # compute next_attempt_at via exponential backoff. Prefer seconds for transient SMTP 4xx.
                    attempts = el.attempt_count
                    transient_code = _extract_smtp_code(e)
                    if attempts >= el.max_attempts:
                        el.next_attempt_at = None
                    else:
                        from datetime import timedelta
                        if transient_code in (421, 450, 451, 452):
                            # start with 30s base, exponential, add small jitter, cap 6h
                            base = 30
                            backoff_seconds = min(60 * 60 * 6, (2 ** (attempts - 1)) * base + random.randint(0, 15))
                            el.next_attempt_at = timezone.now() + timedelta(seconds=backoff_seconds)
                        else:
                            backoff_minutes = min(60 * 6, (2 ** attempts))
                            el.next_attempt_at = timezone.now() + timedelta(minutes=backoff_minutes)
                    el.save(update_fields=['attempt_count', 'last_attempt_at', 'error_text', 'next_attempt_at'])
                    try:
                        msg_text = str(e)
                        if (transient_code == 450 and ('ReceivingRate' in msg_text or 'receiving mail at a rate' in msg_text)):
                            from datetime import timedelta
                            block_minutes = getattr(settings, 'EMAIL_RECIPIENT_RECEIVING_RATE_BLOCK_MINUTES', 1440)
                            block_until = timezone.now() + timedelta(minutes=block_minutes)
                            to_emails = email_message.to or []
                            to_email = (to_emails[0] if to_emails else (el.to_email or '')).strip()
                            if to_email:
                                EmailLog.objects.filter(success=False, to_email__iexact=to_email).update(
                                    next_attempt_at=block_until,
                                    error_text=f'ReceivingRate suppression until {block_until.isoformat()}'
                                )
                                logger.warning('Suppressed further emails to %s until %s due to receiving rate limit', to_email, block_until)
                    except Exception:
                        logger.exception('Bulk suppression update failed for student=%s', student_id)
            else:
                from datetime import timedelta
                attempts = 1
                transient_code = _extract_smtp_code(e)
                if transient_code in (421, 450, 451, 452):
                    base = 30
                    backoff_seconds = min(60 * 60 * 6, (2 ** (attempts - 1)) * base + random.randint(0, 15))
                    next_attempt_at = timezone.now() + timedelta(seconds=backoff_seconds)
                else:
                    backoff_minutes = min(60 * 6, (2 ** attempts))
                    next_attempt_at = timezone.now() + timedelta(minutes=backoff_minutes)
                EmailLog.objects.create(
                    student_id=student_id,
                    contest_id=contest_id,
                    to_email=','.join(email_message.to or []),
                    subject=email_message.subject,
                    success=False,
                    error_text=str(e),
                    attempt_count=1,
                    last_attempt_at=timezone.now(),
                    next_attempt_at=next_attempt_at,
                )
                try:
                    msg_text = str(e)
                    if (transient_code == 450 and ('ReceivingRate' in msg_text or 'receiving mail at a rate' in msg_text)):
                        from datetime import timedelta
                        block_minutes = getattr(settings, 'EMAIL_RECIPIENT_RECEIVING_RATE_BLOCK_MINUTES', 1440)
                        block_until = timezone.now() + timedelta(minutes=block_minutes)
                        to_emails = email_message.to or []
                        to_email = (to_emails[0] if to_emails else '').strip()
                        if to_email:
                            EmailLog.objects.filter(success=False, to_email__iexact=to_email).update(
                                next_attempt_at=block_until,
                                error_text=f'ReceivingRate suppression until {block_until.isoformat()}'
                            )
                            logger.warning('Suppressed further emails to %s until %s due to receiving rate limit', to_email, block_until)
                except Exception:
                    logger.exception('Bulk suppression update failed (no-log path) for student=%s', student_id)
        except Exception:
            logger.exception('Failed to write EmailLog for failure student=%s contest=%s', student_id, contest_id)
        return False


def _extract_smtp_code(exc: Exception):
    """Try to extract SMTP status code from various smtplib exceptions or message strings."""
    try:
        if isinstance(exc, smtplib.SMTPResponseException):
            return getattr(exc, 'smtp_code', None)
        if isinstance(exc, smtplib.SMTPRecipientsRefused):
            # dict of {recipient: (code, errmsg)}
            try:
                values = list(exc.recipients.values())
                if values and isinstance(values[0], tuple) and len(values[0]) >= 1:
                    return int(values[0][0])
            except Exception:
                return None
        # sometimes error text contains code prefix
        msg = str(exc)
        for code in (421, 450, 451, 452):
            if str(code) in msg:
                return code
    except Exception:
        return None
    return None


def notify_students_on_test_completion(contest_id):
    """Enqueue EmailLog entries for all students of a contest when it completes.

    No immediate sending is performed here. Use the `process_email_queue` command to process
    and send emails sequentially with validation and throttling.
    """
    try:
        Contest = apps.get_model('contest', 'Contest')
        Participant = apps.get_model('contest', 'Participant')
        CustomUser = apps.get_model('users', 'CustomUser')
        EmailLog = apps.get_model('contest', 'EmailLog')

        contest = Contest.objects.get(id=contest_id)

        # Respect per-contest toggle for auto emailing
        try:
            if hasattr(contest, 'auto_email_results') and not contest.auto_email_results:
                logger.info('Auto email results disabled for contest=%s; skipping notifications', contest_id)
                return
        except Exception:
            pass

        enrolled_user_ids = set(get_contest_roster_user_ids(contest))

        subject = f"📊 {contest.name} – Performance Summary"
        now = timezone.now()

        from datetime import timedelta
        initial_delay = getattr(settings, 'EMAIL_INITIAL_QUEUE_DELAY_SECONDS', 0)

        created = 0
        for user_id in enrolled_user_ids:
            try:
                student = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                continue

            try:
                next_attempt_at = now + timedelta(seconds=initial_delay) if initial_delay else now
                existing_unsent = EmailLog.objects.filter(
                    student_id=student.id,
                    contest_id=contest.id,
                    subject=subject,
                    success=False,
                ).order_by('id').first()
                if existing_unsent:
                    if not existing_unsent.next_attempt_at or existing_unsent.next_attempt_at < next_attempt_at:
                        existing_unsent.next_attempt_at = next_attempt_at
                        existing_unsent.save(update_fields=['next_attempt_at'])
                else:
                    EmailLog.objects.create(
                        student_id=student.id,
                        contest_id=contest.id,
                        to_email=student.email or '',
                        subject=subject,
                        success=False,
                        attempt_count=0,
                        next_attempt_at=next_attempt_at,
                    )
                    created += 1
            except Exception:
                logger.exception('Failed to enqueue EmailLog for student=%s contest=%s', user_id, contest_id)

        logger.info('Enqueued %s EmailLog entries for contest=%s at %s', created, contest_id, timezone.now())
    except Exception as e:
        logger.exception('Failed to enqueue notifications for contest %s: %s', contest_id, e)


def _compute_rank_map(participant_score_map: dict):
    """Compute tie-aware rank map from a dict of {user_id: score}."""
    sorted_scores = sorted(participant_score_map.items(), key=lambda x: x[1], reverse=True)
    rank_map = {}
    prev_score = None
    rank = 0
    position = 0
    for user_id, score in sorted_scores:
        position += 1
        if score != prev_score:
            rank = position
            prev_score = score
        rank_map[user_id] = rank
    return rank_map


def build_contest_email_context(student, contest):
    """Build validated context for a student's contest email, including marks, attendance, rank, progress, and averages."""
    Participant = apps.get_model('contest', 'Participant')
    # Compute participant scores and averages
    participants = list(Participant.objects.filter(contest=contest).prefetch_related('submissions'))
    participant_score_map = {p.user_id: (p.score or 0) for p in participants}
    scores = list(participant_score_map.values())
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    max_scored = max(scores) if scores else 0
    rank_map = _compute_rank_map(participant_score_map)

    marks = participant_score_map.get(student.id, 0)
    # Present only if there is concrete activity: completed/time_taken/submissions
    attendance = 'Absent'
    try:
        p = next((pp for pp in participants if pp.user_id == student.id), None)
        if p and (p.completed_at or p.time_taken or (hasattr(p, 'submissions') and p.submissions.exists())):
            attendance = 'Present'
    except Exception:
        attendance = 'Present' if student.id in participant_score_map else 'Absent'
    rank = rank_map.get(student.id)
    tutor_name = None
    if getattr(contest, 'tutor', None):
        try:
            tutor_obj = contest.tutor
            tutor_name = (
                getattr(tutor_obj, 'display_name', None)
                or (getattr(tutor_obj, 'user', None) and getattr(tutor_obj.user, 'get_full_name', None) and tutor_obj.user.get_full_name())
                or getattr(tutor_obj, 'name', None)
            )
        except Exception:
            tutor_name = None

    max_marks = contest.max_points or 0
    progress_percent = round(((marks or 0) / max_marks) * 100, 2) if max_marks else 0

    # Simple performance note
    if attendance != 'Present':
        performance_summary = 'You did not attempt this test. We encourage you to participate next time.'
    else:
        try:
            if progress_percent >= 85:
                performance_summary = 'Excellent performance!'
            elif progress_percent >= 60:
                performance_summary = 'Good job! Keep it up.'
            elif progress_percent >= 40:
                performance_summary = 'Fair performance — there\'s room for improvement.'
            else:
                performance_summary = 'Needs improvement.'
        except Exception:
            performance_summary = None

    return {
        'marks': marks,
        'attendance': attendance,
        'rank': rank,
        'avg_score': avg_score,
        'tutor_name': tutor_name,
        'progress_percent': progress_percent,
        'max_scored': max_scored,
        'performance_summary': performance_summary,
    }


def get_contest_roster_user_ids(contest):
    """Return user IDs who should receive the contest email.

    If settings.CONTEST_ROSTER_BACKEND is defined, call it for IDs.
    Otherwise, union of Participant user IDs and M2M `contest.participants` IDs
    to ensure absentees/enrolled users are included.
    """
    try:
        backend_path = getattr(settings, 'CONTEST_ROSTER_BACKEND', None)
        if backend_path:
            mod_name, func_name = backend_path.rsplit('.', 1)
            mod = __import__(mod_name, fromlist=[func_name])
            func = getattr(mod, func_name)
            ids = list(func(contest))
            return ids
    except Exception:
        logger.exception('Failed to call CONTEST_ROSTER_BACKEND; using default roster for contest=%s', contest.id)
    Participant = apps.get_model('contest', 'Participant')
    participant_ids = set(Participant.objects.filter(contest=contest).values_list('user_id', flat=True))
    try:
        enrolled_ids = set(contest.participants.values_list('id', flat=True))
    except Exception:
        enrolled_ids = set()
    return list(participant_ids.union(enrolled_ids))