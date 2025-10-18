from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view
from django.utils.timezone import now
from django.db.models import Sum
from django.core.cache import cache
from rest_framework.permissions import AllowAny

from .models import Contest, Question, Option, Participant, Leaderboard, Submission, SummarizedKeyNote
from .serializers import (
    ContestSerializer,
    QuestionSerializer,
    ParticipantSerializer,
    SubmissionSerializer,
    SummarizedKeyNoteSerializer,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.decorators import permission_classes, action
from django.conf import settings
import os
import logging
from .utils import summarize_question_obj
try:
    from admin_app.utils import broadcast_student_analytics
except Exception:
    broadcast_student_analytics = None

logger = logging.getLogger(__name__)

# Create your views here.

class ContestViewSet(ModelViewSet):
    """
    A viewset for viewing and editing Contest instances.
    """
    queryset = Contest.objects.all().prefetch_related('leaderboards').order_by('-id')
    serializer_class = ContestSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        Retrieves the list of contests, applying caching and filtering based on user role.
        """
        user = self.request.user
        cache_key = f"contest_{user.id if user.is_authenticated else 'public'}"
        cached_contest = cache.get(cache_key)

        if cached_contest is not None:
            return cached_contest

        queryset = Contest.objects.all().order_by('-id')

        # Filtering based on user role
        if user.is_anonymous or not user.is_authenticated:
            queryset = queryset.all()
        elif user.is_staff or user.is_superuser:
            queryset = queryset.all()
        elif hasattr(user, 'role'):
            if user.role == 'tutor':
                queryset = queryset.filter(tutor__user=user)
            elif user.role == 'student':
                queryset = queryset.all()

        cache.set(cache_key, queryset, 60 * 15)  # Cache for 15 minutes
        return queryset

    def perform_create(self, serializer):
        """
        Saves a new contest and invalidates the cache.
        """
        serializer.save()
        self.invalidate_all_cache()

    def perform_destroy(self, instance):
        """
        Deletes a contest and invalidates the cache.
        """
        instance.delete()
        self.invalidate_all_cache()

    def invalidate_all_cache(self):
        """
        Invalidate all cached data.
        """
        cache.clear()

    @action(detail=True, methods=['post'], url_path='participate')
    def participate(self, request, pk=None):
        """
        Allows a user to participate in a contest.
        """
        contest = self.get_object()
        user = request.user

        if contest.status != 'ongoing':
            return Response({'error': 'Contest is not active for participation'}, status=status.HTTP_400_BAD_REQUEST)

        participant, created = Participant.objects.get_or_create(contest=contest, user=user)

        if not created:
            return Response({'error': "You're already participated in this contest"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ParticipantSerializer(participant)
        return Response(serializer.data)

    
class QuestionViewSet(ModelViewSet):
    """
    A viewset for viewing and editing Question instances.
    """
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer


class SubmissionViewSet(ModelViewSet):
    """
    A viewset for viewing and editing Submission instances.
    """
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer

    def create(self, request, *args, **kwargs):
        """
        Handles the submission of answers to questions.
        """
        participant_id = request.data.get('participant_id', '')
        question_id = request.data.get('question_id', '')
        selected_option_id = request.data.get('selected_option_id', '')

        try:
            participant = get_object_or_404(Participant, id=participant_id)
            question = get_object_or_404(Question, id=question_id)
            selected_option = get_object_or_404(Option, id=selected_option_id)
        except Exception:
            return Response({'detail': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

        contest = participant.contest
        current_time = now()
        allowed_time = participant.created_at + contest.time_limit

        if current_time > allowed_time:
            return Response({'detail': 'Time limit exceeded. Cannot submit the answer'}, status=status.HTTP_400_BAD_REQUEST)

        if Submission.objects.filter(participant=participant, question=question).exists():
            return Response({'info': 'You have already submitted this question'}, status=status.HTTP_400_BAD_REQUEST)

        is_correct = selected_option.is_correct

        submission = Submission.objects.create(
            participant=participant,
            question=question,
            selected_option=selected_option,
            is_correct=is_correct
        )

        if is_correct:
            points = contest.max_points / contest.total_questions
            participant.score += points
            participant.save()

        serializer = SubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='stop_or_complete')
    def stop_or_complete(self, request):
        """
        Marks a participant's contest as completed.

        Updates the leaderboard and participant details.
        """
        participant_id = request.data.get('participant_id', '')

        try:
            participant = Participant.objects.get(id=participant_id)
        except Participant.DoesNotExist:
            return Response({'detail' : "Participant not found" }, status=status.HTTP_400_BAD_REQUEST)
        

        participant.completed_at = now()
        participant.time_taken = now() - participant.created_at
        participant.save()

        update_leaderboard(participant.contest)
        # After leaderboard updated and participant completed, generate summaries synchronously
        try:
            from .tasks import generate_summaries_for_contest
            try:
                # Call synchronously so summaries are ready before returning
                generate_summaries_for_contest(participant.contest.id, participant.user.id)
            except Exception as e:
                logger.exception('Synchronous summary generation failed: %s', e)
                # fallback: try to dispatch to Celery if available
                try:
                    generate_summaries_for_contest.delay(participant.contest.id, participant.user.id)
                except Exception as e2:
                    logger.exception('Failed to dispatch Celery generation task: %s', e2)
        except Exception:
            logger.exception('Failed to import generate_summaries_for_contest task')

        return Response({'detail' : 'Contest completed successfully '}, status=status.HTTP_200_OK)


def update_leaderboard(contest):
    """
    Updates the leaderboard for a given contest based on participant scores.

    Ranks participants and saves their scores in the leaderboard.
    """
    participants = Participant.objects.filter(contest=contest).order_by('-score')
    for rank, participant in enumerate(participants, start=1):
        Leaderboard.objects.update_or_create(
            contest=contest,
            user=participant.user,
            defaults={'score': participant.score, 'rank': rank}
        )
        # Broadcast update for this participant to admin channels
        try:
            if broadcast_student_analytics:
                # Prepare minimal analytics payload
                payload = {
                    'user_id': participant.user.id,
                    'contest_id': contest.id,
                    'score': participant.score,
                    'rank': rank,
                }
                broadcast_student_analytics(participant.user.id, payload)
        except Exception:
            pass


class SummarizedKeyNoteViewSet(ReadOnlyModelViewSet):
    """Read-only viewset to list/fetch generated summaries and an action to trigger generation."""
    queryset = None
    serializer_class = SummarizedKeyNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        contest_id = self.request.query_params.get('contest_id')
        if not contest_id:
            return []
        return SummarizedKeyNote.objects.filter(contest_id=contest_id).select_related('question').order_by('question__id')

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """Generate summaries for a contest's questions and save them.

        Only tutors of the contest or enrolled students should be able to trigger; we allow tutors and staff.
        """
        contest_id = request.data.get('contest_id')
        if not contest_id:
            return Response({'detail': 'contest_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            contest = Contest.objects.get(id=contest_id)
        except Contest.DoesNotExist:
            return Response({'detail': 'Contest not found'}, status=status.HTTP_404_NOT_FOUND)

        # permission: only staff, contest tutor, or students who participated can trigger
        user = request.user
        is_tutor = hasattr(user, 'tutor_profile') and contest.tutor and contest.tutor.user_id == user.id
        if not (user.is_staff or is_tutor):
            # allow students only if they participated in contest
            participated = Participant.objects.filter(contest=contest, user=user).exists()
            if not participated:
                return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        # gather notes text: all module notes files content referenced by course modules
        notes_texts = []
        for module in contest.category.courses.first().modules.all() if contest.category and contest.category.courses.exists() else []:
            # if module.notes is a file, try to read small text content; otherwise ignore
            try:
                if module.notes and hasattr(module.notes, 'open'):
                    with module.notes.open('r', encoding='utf-8', errors='ignore') as f:
                        notes_texts.append(f.read())
            except Exception:
                continue

        # mark contest as generating
        try:
            contest.ai_summary_status = 'generating'
            contest.save()
        except Exception:
            pass

        # for each question, (re)generate and save a summary
        summaries = []
        for q in contest.questions.all():
            summary_obj, created = SummarizedKeyNote.objects.get_or_create(contest=contest, question=q)
            # Always regenerate and overwrite summary_text so content is updated
            generated = summarize_question_obj(q, notes_texts)
            summary_obj.summary_text = generated
            summary_obj.generated_by = user
            summary_obj.save()
            summaries.append(summary_obj)

        # mark ready
        try:
            contest.ai_summary_status = 'ready'
            contest.save()
        except Exception:
            pass

        serializer = SummarizedKeyNoteSerializer(summaries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='generate_all')
    def generate_all(self, request):
        """Staff-only: regenerate summaries for all contests.

        This loops through all contests and calls the same summarizer. Intended
        for admins to trigger full-system generation after new notes are uploaded.
        """
        user = request.user
        if not user.is_staff:
            return Response({'detail': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        # Use Django management command to regenerate summaries for all contests
        try:
            # Dispatch to Celery worker to avoid blocking the web request
            from .tasks import regenerate_summaries_command
            regenerate_summaries_command.delay(user.id if user else None)
            return Response({'detail': 'Regeneration queued; running in background'}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            logger.exception('Failed to queue regenerate_summaries task: %s', e)
            return Response({'detail': 'Failed to queue regeneration', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def call_summarizer(prompt: str) -> str:
    # Deprecated - use summarize_question_obj in contest.utils
    return None


@api_view(['GET'])
def global_leaderboard(request):
    """
    Retrieves the global leaderboard showing top participants based on total score.

    Returns the top 10 participants sorted by total score.
    """
    leaderboard = Leaderboard.objects.values('user__username').annotate(
        total_score = Sum('score')
    ).order_by('-total_score')[:5]

    return Response(leaderboard)