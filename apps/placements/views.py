from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Company, Job, JobApplication
from .serializers import (
    CompanySerializer,
    JobApplicationCreateSerializer,
    JobApplicationSerializer,
    JobSerializer,
)

PLACEMENTS_PERMISSION = 'manage_placements'


# ---------------------------------------------------------------------------
# Public / student-facing
# ---------------------------------------------------------------------------

class OpenJobsListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = JobSerializer
    queryset = Job.objects.select_related('company').filter(status='open')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['job_type', 'company']


class MyApplicationsListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = JobApplicationSerializer

    def get_queryset(self):
        return JobApplication.objects.select_related('job__company').filter(student=self.request.user)


class ApplyToJobView(generics.CreateAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = JobApplicationCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save(student=request.user)
        return Response(JobApplicationSerializer(application).data, status=201)


# ---------------------------------------------------------------------------
# Dashboard (RBAC)
# ---------------------------------------------------------------------------

class CompanyListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PLACEMENTS_PERMISSION)]
    serializer_class = CompanySerializer
    queryset = Company.objects.all()


class JobListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PLACEMENTS_PERMISSION)]
    serializer_class = JobSerializer
    queryset = Job.objects.select_related('company').all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'job_type', 'company']


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PLACEMENTS_PERMISSION)]
    serializer_class = JobSerializer
    queryset = Job.objects.select_related('company').all()


class JobApplicationListView(generics.ListAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PLACEMENTS_PERMISSION)]
    serializer_class = JobApplicationSerializer
    queryset = JobApplication.objects.select_related('job__company', 'student')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['job', 'status']


class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PLACEMENTS_PERMISSION)]
    serializer_class = JobApplicationSerializer
    queryset = JobApplication.objects.select_related('job__company', 'student')
