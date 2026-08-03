from admin_security.models import AdminMember, Role
from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember
from certificates.models import Certificate
from courses.models import Course
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from instructors.models import Instructor
from leads.models import Lead
from live_classes.models import LiveSession
from promocodes.models import PromoCode, PromoCodeRedemption
from purchases.models import Purchase
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from students.models import Student
from support.models import Feedback, SupportTicket


def _instructor_profile(user):
    return getattr(user, 'instructor_profile', None)


class DashboardOverviewView(APIView):
    """Landing page stats — scoped the same way as everything else: an
    instructor without `manage_courses` only ever sees numbers for their own
    courses, never platform-wide totals."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('view_dashboard')]

    def get(self, request):
        user = request.user

        if user.has_permission('manage_courses') or user.is_superuser:
            from datetime import timedelta

            courses = Course.objects.all()
            purchases = Purchase.objects.filter(payment_status='completed')

            since = timezone.now() - timedelta(days=180)
            monthly_enrollments = list(
                purchases.filter(created_at__gte=since)
                .annotate(month=TruncMonth('created_at'))
                .values('month')
                .annotate(count=Count('id'))
                .order_by('month')
            )

            return Response({
                'scope': 'platform',
                'total_courses': courses.count(),
                'total_students': Student.objects.count(),
                'total_instructors': Instructor.objects.count(),
                'total_revenue': purchases.aggregate(total=Sum('amount_paid'))['total'] or 0,
                'total_enrollments': purchases.count(),
                'certificates_issued': Certificate.objects.filter(status='issued').count(),
                'active_leads': Lead.objects.filter(is_archived=False).exclude(
                    Q(stage__is_won=True) | Q(stage__is_lost=True)
                ).count(),
                'upcoming_sessions': LiveSession.objects.filter(status='scheduled').count(),
                'monthly_enrollments': monthly_enrollments,
            })

        instructor = _instructor_profile(user)
        if not instructor:
            return Response({
                'scope': 'instructor',
                'total_courses': 0,
                'total_enrollments': 0,
                'total_revenue': 0,
                'upcoming_sessions': 0,
            })

        own_courses = Course.objects.filter(instructor=instructor)
        own_purchases = Purchase.objects.filter(course__instructor=instructor, payment_status='completed')
        return Response({
            'scope': 'instructor',
            'total_courses': own_courses.count(),
            'total_enrollments': own_purchases.count(),
            'total_revenue': own_purchases.aggregate(total=Sum('amount_paid'))['total'] or 0,
            'upcoming_sessions': LiveSession.objects.filter(
                batch__course__instructor=instructor, status='scheduled'
            ).count(),
        })


class DashboardModuleStatsView(APIView):
    """Per-module quick-stat breakdown for the Dashboard "Status" page —
    direct simple queries against each module's own models, same style as
    DashboardOverviewView. Not a rebuild of every module's full analytics
    endpoint, just enough numbers for a glance-able grid."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('view_dashboard')]

    def get(self, request):
        purchases = Purchase.objects.filter(payment_status='completed')

        return Response([
            {
                'name': 'Course Management',
                'data': [
                    {'label': 'Total', 'value': Course.objects.count()},
                    {'label': 'Published', 'value': Course.objects.filter(status='published').count()},
                    {'label': 'Draft', 'value': Course.objects.filter(status='draft').count()},
                ],
            },
            {
                'name': 'Instructor Management',
                'data': [
                    {'label': 'Total', 'value': Instructor.objects.count()},
                    {'label': 'Active', 'value': Instructor.objects.filter(account_status='active').count()},
                ],
            },
            {
                'name': 'Student Management',
                'data': [
                    {'label': 'Total', 'value': Student.objects.count()},
                    {'label': 'Active', 'value': Student.objects.filter(is_active=True).count()},
                    {'label': 'Verified', 'value': Student.objects.filter(is_verified=True).count()},
                ],
            },
            {
                'name': 'Purchases & Enrollment',
                'data': [
                    {'label': 'Enrollments', 'value': purchases.count()},
                    {'label': 'Revenue', 'value': purchases.aggregate(total=Sum('amount_paid'))['total'] or 0},
                ],
            },
            {
                'name': 'Promo Codes',
                'data': [
                    {'label': 'Active', 'value': PromoCode.objects.filter(is_active=True).count()},
                    {'label': 'Redemptions', 'value': PromoCodeRedemption.objects.count()},
                ],
            },
            {
                'name': 'Support & Feedback',
                'data': [
                    {'label': 'Open Tickets', 'value': SupportTicket.objects.filter(status=SupportTicket.STATUS_OPEN).count()},
                    {'label': 'Avg Rating', 'value': round(Feedback.objects.aggregate(avg=Avg('rating'))['avg'] or 0, 1)},
                ],
            },
            {
                'name': 'Admin & Security',
                'data': [
                    {'label': 'Members', 'value': AdminMember.objects.count()},
                    {'label': 'Roles', 'value': Role.objects.count()},
                ],
            },
        ])


class PublicPlatformStatsView(APIView):
    """Real, non-sensitive aggregate counts for the public marketing site
    (Landing Page hero stats) — no revenue/lead numbers, safe for
    unauthenticated exposure."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'total_students': Student.objects.count(),
            'total_courses': Course.objects.filter(status='published').count(),
            'total_instructors': Instructor.objects.filter(admin_verified=True).count(),
            'certificates_issued': Certificate.objects.filter(status='issued').count(),
        })
