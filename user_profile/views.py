import json
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from rest_framework import generics, status, viewsets, views
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import Tutor, Skill, Education, Experience
from users.models import CustomUser
from .serializers import (
    TutorSerializer, EducationSerializer,
    ExperienceSerializer, CourseSalesSerializer
)
from base.custom_permissions import IsAdmin, IsStudent, IsTutor
from course.models import Course, StudentCourseProgress, Transaction, Module, Review
from course.serializers import (
    TransactionSerializer, ReviewSerializer, StudentCourseProgressSerializer
)
from contest.models import Contest, Participant, Leaderboard
from contest.serializers import LeaderboardSerializer
from .validation import TutorProfileValidator
from django.shortcuts import get_object_or_404

# Create your views here.


class TutorProfile(APIView):
    """
    API view for creating and listing tutor profiles.
    """

    def post(self, request):
        """
        Create a new tutor profile.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: The HTTP response object.
        """
        data = request.data.copy()  
        validator = TutorProfileValidator(data)
        validation_errors = validator.validate()

        if validation_errors:
            return Response({'error': validation_errors}, status=status.HTTP_400_BAD_REQUEST)

        # Process JSON fields
        json_fields = ['education', 'experiences']
        for field in json_fields:
            if field in data:
                try:
                    data[field] = json.loads(data[field][0] if isinstance(data[field], list) else data[field])
                except json.JSONDecodeError as e:
                    return Response({'error': f'Invalid JSON in {field}: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if 'skills' in data and isinstance(data['skills'], list) and len(data['skills']) == 1:
                data['skills'] = data['skills'][0].split(',')  
        except json.JSONDecodeError as e:
            return Response({'error': f'Invalid JSON: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


        # Update user data
        if 'email' in data:
            try:
                user = CustomUser.objects.get(email=data['email'])

            except CustomUser.DoesNotExist:
                return Response(data={'error' : 'User not Found'}, status=status.HTTP_404_NOT_FOUND)
            
            data['userId'] = user.id
            user_fields = ['first_name', 'last_name', 'phone', 'bio', 'dob', 'profile']
            for field in user_fields:
                if field in data:
                    setattr(user, field, data[field])
            user.save()

        # Create tutor profile
        tutor_serializer = TutorSerializer(data=data)
        if tutor_serializer.is_valid():
            try:
                with transaction.atomic():
                    tutor = tutor_serializer.save()
                    return Response(tutor_serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error' : str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(tutor_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def get(self, request):
        """
        List all tutor profile

        Args:
            request (Request) : The HTTP request object

        Returns:
            Response: The HTTP response object containing all tutor profile
        """
        data = Tutor.objects.all().select_related('user')
        serializer = TutorSerializer(data, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
    

class TutorDetails(generics.RetrieveUpdateAPIView):
    """
    API view for retrieving and updating tutor details.
    """
    queryset = Tutor.objects.all()
    serializer_class = TutorSerializer
    permission_classes = [IsAdmin | IsTutor]

    def update(self, request, *args, **kwargs):
        """
        Update tutor details and send email if status changes.

        Args:
            request (Request): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: The HTTP response object.
        """
        instance = self.get_object()
        old_status = instance.status
        response = super().update(request, *args, **kwargs)
        new_status = request.data.get('status')

        if old_status != new_status:
            self.send_change_status_email(instance, new_status)
        return response

    def send_change_status_email(self, tutor, new_status):
        """
        Send a professional HTML email to tutor when their application status changes.
        """
        subject = 'Update on Your Application Status'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient = [tutor.user.email]

        # Define message context
        if new_status == 'Verified':
            message = "Congratulations! Your application has been accepted."
            status_message = "Accepted ✅"
            highlight_color = "#16a34a"  # green
        elif new_status == 'Rejected':
            message = "We're sorry to inform you that your application has been rejected."
            status_message = "Rejected ❌"
            highlight_color = "#dc2626"  # red
        else:
            message = f"Your application status has been updated to {new_status}."
            status_message = new_status
            highlight_color = "#2563eb"  # blue (default)

        context = {
            "tutor_name": tutor.user.get_full_name() or tutor.user.username,
            "message": message,
            "status_message": status_message,
            "highlight_color": highlight_color,
        }

        # Render templates
        text_content = render_to_string("emails/status_update_email.txt", context)
        html_content = render_to_string("emails/status_update_email.html", context)

        # Send both text and HTML versions
        email = EmailMultiAlternatives(subject, text_content, from_email, recipient)
        email.attach_alternative(html_content, "text/html")

        try:
            email.send()
            print(f"✅ Status update email sent to {recipient}")
        except Exception as e:
            print(f"❌ Failed to send status update email to {recipient}: {e}")
    

class MyProfileViewSets(viewsets.ModelViewSet):
    """
    Viewset for managing a tutor's own profile  
    """
    queryset = Tutor.objects.all()
    serializer_class = TutorSerializer
    permission_classes = [IsTutor]

    def get_queryset(self):
        """
        Get queryset for the current user's tutor profile
        
        Returns:
            Queryset: The filtered queryset for the current user
        """
        return Tutor.objects.filter(user=self.request.user)


class SkillEditView(APIView):
    """
    API View for editing tutor skills
    """
    def patch(self, request,id, *args, **kwargs):
        """
        Update tutor skills.

        Args:
            request (Request): The HTTP request object.
            id (int): The ID of the tutor.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: The HTTP response object.
        """
        skills_data = request.data.get('skills', [])
        tutor = request.user.tutor_profile
        for skill in skills_data:
            Skill.objects.filter(tutor=tutor, id=skill['id']).update(skill_name=skill['skill_name'])
        return Response({'success': 'Skills updated'})


class EducationEditView(views.APIView):
    """
    API View for editing tutor education 
    """
    def patch(self, request,id, *args, **kwargs):
        """
        Update tutor education.

        Args:
            request (Request): The HTTP request object.
            id (int): The ID of the education entry.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: The HTTP response object.
        """
        try:
            edu = Education.objects.get(id=id)
        except Education.DoesNotExist:
            return Response({'error' : 'Education not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = EducationSerializer(edu, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

class ExperienceEditView(views.APIView):
    """
    API view for editing tutor experience.
    """
    def patch(self, request,id, *args, **kwargs):
        """
        Update tutor experience.

        Args:
            request (Request): The HTTP request object.
            id (int): The ID of the experience entry.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: The HTTP response object.
        """
        try:
            edu = Experience.objects.get(id=id)
        except Experience.DoesNotExist:
            return Response({'error' : 'Education not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ExperienceSerializer(edu, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TutorDashboardView(viewsets.ViewSet):
    """
    ViewSet for tutor dashboard data.
    """
    def list(self, request):
        """
        Retrieve dashboard data for a tutor.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: The HTTP response object containing dashboard data.
        """
        tutor = request.user.tutor_profile

        # Aggregate statistics
        total_course = Course.objects.filter(tutor=tutor).count()
        enrolled_course = StudentCourseProgress.objects.filter(course__tutor=tutor).count()
        total_amount = Transaction.objects.filter(course__tutor=tutor).aggregate(total=Sum('amount'))['total'] or 0
        total_views = Module.objects.filter(course__tutor=tutor).aggregate(total_view_count=Sum('views_count'))['total_view_count'] or 0

        # Course progress statistics
        completed_course = StudentCourseProgress.objects.filter(course__tutor=tutor, progress='Completed').count()
        ongoing_course = StudentCourseProgress.objects.filter(course__tutor=tutor, progress='Ongoing').count()
        not_started_course = StudentCourseProgress.objects.filter(course__tutor=tutor, progress='Not Started').count()      

        # Recent data
        recent_purchase = Transaction.objects.filter(course__tutor=tutor).order_by('-id')[:5]
        recent_reviews = Review.objects.filter(course__tutor=tutor).order_by('-id')[:5]
        recent_enrollments = StudentCourseProgress.objects.filter(course__tutor=tutor).order_by('-created_at')[:5]
        recent_contests = Leaderboard.objects.filter(contest__tutor=tutor).order_by('created_at')[:5]

        # Serialize recent data
        recent_purchase_serializer = TransactionSerializer(recent_purchase, many=True)
        review_data_serializer = ReviewSerializer(recent_reviews, many=True, context={'request': request})
        recent_enrollment_serializer = StudentCourseProgressSerializer(recent_enrollments, many=True, context={'request': request})
        recent_contest_serializer = LeaderboardSerializer(recent_contests, many=True)


        # Monthly enrollment data
        monthly_enrollments = (
            StudentCourseProgress.objects
            .filter(course__tutor=tutor)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        enrollment_data = [0] * 12
        for entry in monthly_enrollments:
            month = entry['month'].month - 1
            enrollment_data[month] = entry['count']

        # Prepare response data
        response_data = {
            "stats": {
                "total_courses": total_course,
                "enrolled_courses": enrolled_course,
                "total_amount": total_amount,
                "total_views": total_views
            },
            "progress": {
                "completed_course": completed_course,
                "ongoing_course": ongoing_course,
                "not_started_course": not_started_course
            },
            "recent_purchase": recent_purchase_serializer.data,
            "recent_reviews": review_data_serializer.data,
            "recent_enrollments": recent_enrollment_serializer.data,
            "recent_contests": recent_contest_serializer.data,
            "enrollment_data": enrollment_data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class TutorSalesReport(viewsets.ViewSet):
    """
    ViewSet for generating tutor sales reports.
    """
    def list(self, request):
        """
        Generate a sales report for a tutor within a specified date range.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: The HTTP response object containing the sales report data.
        """
        tutor = request.user.tutor_profile
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')

        if start_date and end_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', ''))
                end_date = datetime.fromisoformat(end_date.replace('Z', ''))

                sales_report_data = Transaction.objects.filter(
                    course__tutor=tutor,
                    created_at__range=(start_date, end_date)
                ).values(
                    'course_id',
                    'course__title'
                ).annotate(
                    total_sales=Count('id'),
                    total_amount=Sum('amount'))
                                
                sales_report =  CourseSalesSerializer(sales_report_data, many=True)

                return Response({"sales": sales_report.data}, status=status.HTTP_200_OK)
            except ValueError:
                return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)


class StudentAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet to provide student analytics data for tutors.
    """
    def list(self, request):
        # Return list of students with basic aggregated metrics and time-series placeholders
        students = CustomUser.objects.filter(role='student').select_related()
        data = []
        for s in students:
            enrolled = StudentCourseProgress.objects.filter(student=s)
            contests = Leaderboard.objects.filter(user=s)
            total_study_hours = enrolled.aggregate(total_hours=Sum('watch_time'))['total_hours'] or 0
            completion_pct = 0
            total_courses = enrolled.count()
            if total_courses:
                completed = enrolled.filter(progress='Completed').count()
                completion_pct = int((completed / total_courses) * 100)

            data.append({
                'id': s.id,
                'name': s.username or s.first_name,
                'email': s.email,
                'enrolled_courses_count': total_courses,
                'total_study_hours': total_study_hours,
                'completion_pct': completion_pct,
                'total_tests': contests.count(),
                'contest_scores': list(contests.values('score', 'rank', 'contest_id'))
            })

        # time-series placeholders
        time_series = {
            'enrollments_over_time': [],
            'scores_trend': []
        }

        aggregated = {
            'total_students': students.count(),
            'average_score': Leaderboard.objects.aggregate(avg_score=Sum('score'))['avg_score'] or 0,
            'top_performers': list(Leaderboard.objects.order_by('-score')[:5].values('user__username','score'))
        }

        return Response({'students': data, 'aggregated': aggregated, 'time_series': time_series}, status=status.HTTP_200_OK)


class StudentDetailAnalytics(views.APIView):
    """
    Return detailed analytics for a single student.
    Endpoint: /api/students/<id>/analytics/
    """
    def get(self, request, pk):
        student = get_object_or_404(CustomUser, pk=pk, role='student')

        # Enrolled courses with progress and watch_time
        enrolled = StudentCourseProgress.objects.filter(student=student).select_related('course')
        courses = []
        for e in enrolled:
            courses.append({
                'id': e.course.id,
                'title': e.course.title,
                'progress': e.progress,
                'watch_time': e.watch_time,
                'started_at': e.created_at,
                'updated_at': e.updated_at
            })


        # Contests/tests conducted by this tutor and student's participation (present or absent)
        # Assumption: tutor is viewing students; if tutor profile missing, fall back to all contests
        tutor = getattr(request.user, 'tutor_profile', None)
        if tutor:
            contests_qs = Contest.objects.filter(tutor=tutor).order_by('-start_time')
        else:
            contests_qs = Contest.objects.all().order_by('-start_time')

        # Fetch participant and leaderboard entries for this student across those contests
        participant_qs = Participant.objects.filter(user=student, contest__in=contests_qs)
        leaderboard_qs = Leaderboard.objects.filter(user=student, contest__in=contests_qs)

        part_map = {p.contest_id: p for p in participant_qs}
        lb_map = {l.contest_id: l for l in leaderboard_qs}

        contests_details = []
        for c in contests_qs:
            max_marks = c.max_points or 0
            part = part_map.get(c.id)
            lb = lb_map.get(c.id)

            student_marks = 0
            attendance = 'Absent'
            rank = None

            if part:
                student_marks = getattr(part, 'score', 0) or 0
                attendance = 'Present'
            if lb:
                # leaderboard may store authoritative rank/score
                student_marks = getattr(lb, 'score', student_marks) or student_marks
                rank = getattr(lb, 'rank', None)
                attendance = 'Present'

            progress_pct = 0
            if max_marks > 0:
                try:
                    progress_pct = round((student_marks / float(max_marks)) * 100, 2)
                except Exception:
                    progress_pct = 0

            date_conducted = c.start_time or c.end_time or c.created_at

            contests_details.append({
                'id': c.id,
                'title': c.name,
                'date_conducted': date_conducted,
                'max_marks': max_marks,
                'student_marks': student_marks,
                'attendance_status': attendance,
                'rank': rank,
                'progress_percentage': progress_pct
            })

        # Summary analytics for contests/tests
        total_tests = contests_qs.count()
        attempted_tests = sum(1 for d in contests_details if d['attendance_status'] == 'Present')
        avg_score = 0
        if attempted_tests > 0:
            avg_score = round(sum(d['student_marks'] for d in contests_details if d['attendance_status'] == 'Present') / attempted_tests, 2)
        attendance_pct = round((attempted_tests / total_tests) * 100, 2) if total_tests > 0 else 0
        best = None
        present_entries = [d for d in contests_details if d['attendance_status'] == 'Present']
        if present_entries:
            best_entry = max(present_entries, key=lambda x: x['student_marks'])
            best = {'title': best_entry['title'], 'score': best_entry['student_marks'], 'rank': best_entry['rank']}

        # time-series for charts
        scores_trend = [{'date': d['date_conducted'], 'score': d['student_marks']} for d in sorted(contests_details, key=lambda x: x['date_conducted'] or datetime.min)]
        attendance_ratio = {'present': attempted_tests, 'absent': total_tests - attempted_tests}

        # Course breakdown
        total = enrolled.count()
        completed = enrolled.filter(progress='Completed').count()
        ongoing = enrolled.filter(progress='Ongoing').count()
        not_started = enrolled.filter(progress='Not Started').count()

        response = {
            'student': {
                'id': student.id,
                'name': student.first_name or student.username,
                'email': student.email
            },
            'courses': courses,
            'contests': contests_details,
            'tests_summary': {
                'total_tests': total_tests,
                'tests_attempted': attempted_tests,
                'average_score': avg_score,
                'attendance_percentage': attendance_pct,
                'best': best
            },
            'tests_time_series': {
                'scores_trend': scores_trend,
                'attendance_ratio': attendance_ratio
            },
            'performance': {
                'average_score': avg_score,
                'breakdown': {
                    'completed': completed,
                    'ongoing': ongoing,
                    'not_started': not_started,
                    'total': total
                }
            }
        }
        return Response(response, status=status.HTTP_200_OK)