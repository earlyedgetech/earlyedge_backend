from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from django.db.models import Count, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Challenge, ChallengeSubmission
from .serializers import ChallengeSerializer, ChallengeSubmissionSerializer, LeaderboardEntrySerializer

CHALLENGES_PERMISSION = 'manage_challenges'


# ---------------------------------------------------------------------------
# Public / student-facing
# ---------------------------------------------------------------------------

class ActiveChallengesListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ChallengeSerializer
    queryset = Challenge.objects.filter(is_active=True)


class MySubmissionsListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = ChallengeSubmissionSerializer

    def get_queryset(self):
        return ChallengeSubmission.objects.select_related('challenge').filter(student=self.request.user)


class SubmitChallengeView(generics.CreateAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = ChallengeSubmissionSerializer

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class LeaderboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        rows = (
            ChallengeSubmission.objects.filter(status='passed')
            .values('student_id', 'student__full_name')
            .annotate(total_score=Sum('score'), challenges_completed=Count('id'))
            .order_by('-total_score')[:50]
        )
        data = [
            {
                'student_id': row['student_id'],
                'student_name': row['student__full_name'],
                'total_score': row['total_score'] or 0,
                'challenges_completed': row['challenges_completed'],
            }
            for row in rows
        ]
        return Response(LeaderboardEntrySerializer(data, many=True).data)


# ---------------------------------------------------------------------------
# Dashboard (RBAC)
# ---------------------------------------------------------------------------

class ChallengeListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(CHALLENGES_PERMISSION)]
    serializer_class = ChallengeSerializer
    queryset = Challenge.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['difficulty', 'is_active']


class ChallengeDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(CHALLENGES_PERMISSION)]
    serializer_class = ChallengeSerializer
    queryset = Challenge.objects.all()


class SubmissionListView(generics.ListAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(CHALLENGES_PERMISSION)]
    serializer_class = ChallengeSubmissionSerializer
    queryset = ChallengeSubmission.objects.select_related('challenge', 'student')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['challenge', 'status']


class SubmissionGradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChallengeSubmission
        fields = ['id', 'status', 'score']
        read_only_fields = ['id']


class SubmissionDetailView(generics.RetrieveUpdateAPIView):
    """Admin grades a submission (status/score)."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(CHALLENGES_PERMISSION)]
    queryset = ChallengeSubmission.objects.select_related('challenge', 'student')
    serializer_class = SubmissionGradeSerializer
