import csv

import django_filters
from admin_security.models import AdminMember
from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import IsAdminMember
from common.exports import export_rows
from common.integrations.zoom_client import ZoomClient
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import load_workbook
from rest_framework import filters, generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .automations import run_automations
from .models import (
    AutomationRule,
    CounsellingSession,
    Lead,
    LeadActivity,
    LeadCustomFieldDefinition,
    LeadDocument,
    LeadFollowUp,
    LeadSettings,
    LeadSource,
    LeadStageHistory,
    PipelineStage,
)
from .serializers import (
    AutomationRuleSerializer,
    CounsellingSessionSerializer,
    LeadCustomFieldDefinitionSerializer,
    LeadDetailSerializer,
    LeadDocumentSerializer,
    LeadFollowUpSerializer,
    LeadPublicCreateSerializer,
    LeadSerializer,
    LeadSettingsSerializer,
    LeadSourceSerializer,
    PipelineStageSerializer,
)

DETAIL_QS = Lead.objects.select_related('source', 'interested_course', 'assigned_to', 'stage').prefetch_related(
    'follow_ups', 'counselling_sessions', 'documents', 'activities', 'stage_history__from_stage', 'stage_history__to_stage',
)


class HasLeadsAccess(BasePermission):
    """`manage_leads` (full access) OR the specific granular codename for
    this view/method — mirrors the manage_courses/manage_own_courses dual
    check used elsewhere, but for CRUD-level granularity within one app."""

    def __init__(self, codename):
        self.codename = codename

    def __call__(self):
        return self

    def has_permission(self, request, view):
        user = request.user
        return (
            isinstance(user, AdminMember)
            and user.is_authenticated
            and (user.has_permission('manage_leads') or user.has_permission(self.codename))
        )


def _log_activity(lead, actor, activity_type, description=''):
    LeadActivity.objects.create(lead=lead, actor=actor, activity_type=activity_type, description=description)


def _duplicate_query(email, phone):
    query = Q()
    if email:
        query |= Q(email__iexact=email)
    if phone:
        query |= Q(phone=phone)
    return query


# ---------------------------------------------------------------------------
# Counsellor options (no AdminMember-listing endpoint exists anywhere else
# in the backend to reuse — this is a minimal read-only list for the
# "assign to counsellor" pickers, not a Members-management CRUD surface,
# which belongs to admin_security and is out of scope here).
# ---------------------------------------------------------------------------

class CounsellorOptionsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('view_leads')]

    def get(self, request):
        members = AdminMember.objects.filter(is_active=True).order_by('full_name').values('id', 'full_name', 'email')
        return Response(list(members))


# ---------------------------------------------------------------------------
# Pipeline Stages
# ---------------------------------------------------------------------------

class PipelineStageListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = PipelineStageSerializer
    queryset = PipelineStage.objects.all()
    pagination_class = None


class PipelineStageDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = PipelineStageSerializer
    queryset = PipelineStage.objects.all()


# ---------------------------------------------------------------------------
# Lead Sources
# ---------------------------------------------------------------------------

class LeadSourceListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadSourceSerializer
    queryset = LeadSource.objects.all()
    pagination_class = None


class LeadSourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadSourceSerializer
    queryset = LeadSource.objects.all()


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

class LeadFilter(django_filters.FilterSet):
    class Meta:
        model = Lead
        fields = ['stage', 'source', 'assigned_to', 'priority']


class LeadListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = LeadFilter
    search_fields = ['full_name', 'email', 'phone']

    def get_permissions(self):
        codename = 'create_leads' if self.request.method == 'POST' else 'view_leads'
        return [IsAdminMember(), HasLeadsAccess(codename)]

    def get_queryset(self):
        queryset = Lead.objects.select_related('source', 'interested_course', 'assigned_to', 'stage')
        show_archived = self.request.query_params.get('archived') == 'true'
        return queryset.filter(is_archived=show_archived)

    def perform_create(self, serializer):
        lead = serializer.save()
        _log_activity(lead, self.request.user, 'created', f'Created by {self.request.user.full_name}.')
        run_automations('new_lead_created', lead)


class LeadDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    queryset = DETAIL_QS

    def get_serializer_class(self):
        return LeadDetailSerializer if self.request.method == 'GET' else LeadSerializer

    def get_permissions(self):
        codename = {'DELETE': 'delete_leads', 'GET': 'view_leads'}.get(self.request.method, 'edit_leads')
        return [IsAdminMember(), HasLeadsAccess(codename)]

    def perform_update(self, serializer):
        old_stage_id = serializer.instance.stage_id
        old_assigned_id = serializer.instance.assigned_to_id
        lead = serializer.save()

        if 'stage' in self.request.data and lead.stage_id != old_stage_id:
            LeadStageHistory.objects.create(
                lead=lead, from_stage_id=old_stage_id, to_stage=lead.stage, changed_by=self.request.user,
            )
            _log_activity(
                lead, self.request.user, 'stage_changed',
                f'Moved to {lead.stage.name if lead.stage else "no stage"}.',
            )
            run_automations('stage_changed', lead)

        if 'assigned_to' in self.request.data and lead.assigned_to_id != old_assigned_id:
            _log_activity(
                lead, self.request.user, 'assigned',
                f'Assigned to {lead.assigned_to.full_name if lead.assigned_to else "unassigned"}.',
            )
            if lead.assigned_to:
                from .automations import _notify_lead_assigned

                _notify_lead_assigned(lead, lead.assigned_to)

        if 'notes' in self.request.data:
            _log_activity(lead, self.request.user, 'note_added')

        if 'is_archived' in self.request.data:
            _log_activity(lead, self.request.user, 'archived' if lead.is_archived else 'note_added',
                           'Archived.' if lead.is_archived else 'Restored from archive.')


class LeadDuplicateCheckView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('view_leads')]

    def get(self, request):
        email = (request.query_params.get('email') or '').strip()
        phone = (request.query_params.get('phone') or '').strip()
        query = _duplicate_query(email, phone)
        if not query:
            return Response({'duplicates': []})
        matches = Lead.objects.filter(query, is_archived=False)[:5]
        return Response({'duplicates': LeadSerializer(matches, many=True).data})


class LeadMergeView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]

    def post(self, request, pk):
        source = get_object_or_404(Lead, pk=pk)
        target_id = request.data.get('merge_into')
        if not target_id:
            raise ValidationError('merge_into is required.')
        target = get_object_or_404(Lead, pk=target_id)
        if source.id == target.id:
            raise ValidationError('Cannot merge a lead into itself.')

        source.follow_ups.update(lead=target)
        source.counselling_sessions.update(lead=target)
        source.documents.update(lead=target)
        source.activities.update(lead=target)

        _log_activity(
            target, request.user, 'merged',
            f'Merged lead #{source.id} ({source.full_name}) into this lead.',
        )
        source.is_archived = True
        source.save(update_fields=['is_archived'])

        return Response(LeadDetailSerializer(DETAIL_QS.get(pk=target.id)).data)


class LeadExportView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('export_leads')]

    HEADERS = ['ID', 'Full Name', 'Email', 'Phone', 'Source', 'Course', 'Stage', 'Priority', 'Assigned To', 'Created At']
    FIELDS = [
        'id', 'full_name', 'email', 'phone', 'source_name', 'interested_course_title',
        'stage_name', 'priority', 'assigned_to_name', 'created_at',
    ]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = Lead.objects.select_related('source', 'interested_course', 'assigned_to', 'stage').filter(is_archived=False)
        ids_param = request.query_params.get('ids')
        if ids_param:
            ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
            queryset = queryset.filter(id__in=ids)

        rows = LeadSerializer(queryset, many=True).data
        if not rows:
            return Response({'detail': 'No matching leads to export.'}, status=400)
        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'leads')


class LeadBulkActionView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]

    def post(self, request):
        ids = request.data.get('ids') or []
        action = request.data.get('action')
        if not ids or not action:
            raise ValidationError('ids and action are required.')
        queryset = Lead.objects.filter(id__in=ids)

        if action == 'delete':
            if not (request.user.has_permission('manage_leads') or request.user.has_permission('delete_leads')):
                raise PermissionDenied('You do not have permission to delete leads.')
            count = queryset.count()
            queryset.delete()
            return Response({'deleted': count})

        if action == 'archive':
            count = queryset.update(is_archived=True)
            return Response({'archived': count})

        if action == 'restore':
            count = queryset.update(is_archived=False)
            return Response({'restored': count})

        if action == 'assign':
            count = queryset.update(assigned_to_id=request.data.get('assigned_to') or None)
            return Response({'assigned': count})

        if action == 'stage':
            count = queryset.update(stage_id=request.data.get('stage') or None)
            return Response({'updated': count})

        raise ValidationError('Unknown action.')


class LeadAutoAssignUnassignedView(APIView):
    """Sweeps every currently-unassigned lead through Lead Settings >
    Assignment strategy — the "fix the backlog" counterpart to
    automations.apply_default_assignment, which only runs for newly-created
    leads. Lets an admin apply a newly-configured strategy (e.g. switching
    Website leads to a specific counsellor) to leads that already exist."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]

    def post(self, request):
        from .automations import _notify_lead_assigned, resolve_strategy_assignee

        settings = LeadSettings.get_solo()
        if settings.assignment_strategy == 'manual':
            return Response(
                {'assigned': 0, 'detail': 'Assignment strategy is set to Manual — nothing to auto-assign.'}
            )

        unassigned = Lead.objects.filter(assigned_to__isnull=True, is_archived=False).select_related('source')
        assigned_count = 0
        for lead in unassigned:
            assignee = resolve_strategy_assignee(lead, settings)
            if not assignee:
                continue
            lead.assigned_to = assignee
            lead.save(update_fields=['assigned_to'])
            _log_activity(
                lead, request.user, 'assigned',
                f'Auto-assigned to {assignee.full_name} ({settings.get_assignment_strategy_display()}) '
                f'via unassigned-leads sweep.',
            )
            _notify_lead_assigned(lead, assignee)
            assigned_count += 1

        return Response({'assigned': assigned_count, 'remaining_unassigned': unassigned.count() - assigned_count})


class LeadImportView(APIView):
    """CSV/Excel bulk import — case-insensitive header mapping + the same
    duplicate check as the single-lead form."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('import_leads')]
    parser_classes = [MultiPartParser, FormParser]

    FIELD_ALIASES = {
        'full_name': ['full_name', 'full name', 'name', 'fullname'],
        'email': ['email', 'email address'],
        'phone': ['phone', 'mobile', 'mobile number', 'phone number'],
        'parent_name': ['parent_name', 'parent name'],
        'parent_contact': ['parent_contact', 'parent contact'],
        'city': ['city'],
        'state': ['state'],
        'country': ['country'],
        'notes': ['notes'],
    }

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError('file is required.')

        source_id = request.data.get('source') or None
        rows = self._parse_excel(file_obj) if file_obj.name.lower().endswith('.xlsx') else self._parse_csv(file_obj)

        created, skipped, errors = 0, 0, []
        for index, row in enumerate(rows, start=2):
            full_name = (row.get('full_name') or '').strip()
            email = (row.get('email') or '').strip()
            phone = (row.get('phone') or '').strip()
            if not full_name:
                errors.append({'row': index, 'reason': 'full_name is required'})
                continue

            query = _duplicate_query(email, phone)
            if query and Lead.objects.filter(query).exists():
                skipped += 1
                continue

            lead = Lead.objects.create(
                full_name=full_name, email=email, phone=phone,
                parent_name=(row.get('parent_name') or '').strip(),
                parent_contact=(row.get('parent_contact') or '').strip(),
                city=(row.get('city') or '').strip(), state=(row.get('state') or '').strip(),
                country=(row.get('country') or '').strip(), notes=(row.get('notes') or '').strip(),
                source_id=source_id,
            )
            _log_activity(lead, request.user, 'created', 'Created via import.')
            created += 1

        return Response({'created': created, 'skipped_duplicates': skipped, 'errors': errors})

    def _normalize_headers(self, raw_headers):
        reverse_map = {}
        for field, aliases in self.FIELD_ALIASES.items():
            for alias in aliases:
                reverse_map[alias] = field
        return [reverse_map.get((h or '').strip().lower()) for h in raw_headers]

    def _parse_csv(self, file_obj):
        decoded = file_obj.read().decode('utf-8-sig').splitlines()
        reader = csv.reader(decoded)
        headers = self._normalize_headers(next(reader, []))
        rows = []
        for raw_row in reader:
            rows.append({key: value for key, value in zip(headers, raw_row) if key})
        return rows

    def _parse_excel(self, file_obj):
        workbook = load_workbook(file_obj, read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        headers = self._normalize_headers(list(next(rows_iter, [])))
        rows = []
        for raw_row in rows_iter:
            rows.append({
                key: (str(value) if value is not None else '')
                for key, value in zip(headers, raw_row) if key
            })
        return rows


# ---------------------------------------------------------------------------
# Public (website enquiry form + generic webhook)
# ---------------------------------------------------------------------------

class LeadPublicEnquiryView(generics.CreateAPIView):
    """Real endpoint behind the website's lead-capture form."""

    permission_classes = [AllowAny]
    serializer_class = LeadPublicCreateSerializer

    def perform_create(self, serializer):
        source, _ = LeadSource.objects.get_or_create(name='Website')
        default_stage = PipelineStage.objects.order_by('order').first()
        lead = serializer.save(source=source, stage=default_stage)
        _log_activity(lead, None, 'created', 'Submitted via website enquiry form.')
        run_automations('new_lead_created', lead)


class LeadWebhookView(APIView):
    """Generic, vendor-agnostic inbound webhook — any tool that can POST
    JSON with a shared secret can feed leads in without a dedicated
    integration. `source_id` identifies which LeadSource (and secret) to use."""

    permission_classes = [AllowAny]

    def post(self, request, source_id):
        source = get_object_or_404(LeadSource, pk=source_id)
        provided_secret = request.headers.get('X-Webhook-Secret', '')
        if not source.webhook_secret or provided_secret != source.webhook_secret:
            raise PermissionDenied('Invalid or missing webhook secret.')

        full_name = (request.data.get('full_name') or '').strip()
        if not full_name:
            raise ValidationError('full_name is required.')

        default_stage = PipelineStage.objects.order_by('order').first()
        lead = Lead.objects.create(
            full_name=full_name,
            email=request.data.get('email', ''),
            phone=request.data.get('phone', ''),
            notes=request.data.get('message', ''),
            source=source,
            stage=default_stage,
        )
        _log_activity(lead, None, 'created', f'Received via {source.name} webhook.')
        run_automations('new_lead_created', lead)
        return Response({'id': lead.id}, status=201)


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

class LeadFollowUpListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadFollowUpSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['lead', 'is_completed', 'follow_up_type']
    queryset = LeadFollowUp.objects.select_related('lead', 'created_by')

    def perform_create(self, serializer):
        follow_up = serializer.save(created_by=self.request.user)
        _log_activity(follow_up.lead, self.request.user, 'follow_up', f'Follow-up scheduled for {follow_up.follow_up_date}.')


class LeadFollowUpDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadFollowUpSerializer
    queryset = LeadFollowUp.objects.select_related('lead', 'created_by')

    def perform_update(self, serializer):
        was_completed = serializer.instance.is_completed
        follow_up = serializer.save()
        if follow_up.is_completed and not was_completed:
            _log_activity(follow_up.lead, self.request.user, 'follow_up', 'Follow-up completed.')
            if follow_up.next_follow_up_date:
                LeadFollowUp.objects.create(
                    lead=follow_up.lead, follow_up_type=follow_up.follow_up_type,
                    note='Auto-scheduled from previous follow-up outcome.',
                    follow_up_date=follow_up.next_follow_up_date, created_by=self.request.user,
                )
            run_automations('follow_up_completed', follow_up.lead)


# ---------------------------------------------------------------------------
# Counselling
# ---------------------------------------------------------------------------

class CounsellingSessionListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = CounsellingSessionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['lead', 'counsellor', 'mode']
    queryset = CounsellingSession.objects.select_related('lead', 'counsellor', 'course_discussed')

    def perform_create(self, serializer):
        session = serializer.save()
        if session.mode == 'online':
            meeting = ZoomClient().create_meeting(
                topic=f'Counselling — {session.lead.full_name}',
                start_time=session.scheduled_at,
                duration_minutes=45,
            )
            session.meeting_url = meeting['join_url']
            session.save(update_fields=['meeting_url'])
        _log_activity(session.lead, self.request.user, 'follow_up', f'Counselling session scheduled for {session.scheduled_at}.')


class CounsellingSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = CounsellingSessionSerializer
    queryset = CounsellingSession.objects.select_related('lead', 'counsellor', 'course_discussed')

    def perform_update(self, serializer):
        had_outcome = bool(serializer.instance.outcome)
        session = serializer.save()
        if session.outcome and not had_outcome:
            _log_activity(session.lead, self.request.user, 'follow_up', f'Counselling outcome: {session.get_outcome_display()}.')
            outcome_to_stage = {
                'interested': 'Interested', 'demo_required': 'Demo Scheduled',
                'admission_ready': 'Enrolled', 'retry': 'Retry', 'lost': 'Lost',
            }
            stage_name = outcome_to_stage.get(session.outcome)
            if stage_name:
                stage = PipelineStage.objects.filter(name=stage_name).first()
                if stage and session.lead.stage_id != stage.id:
                    old_stage_id = session.lead.stage_id
                    session.lead.stage = stage
                    session.lead.save(update_fields=['stage'])
                    LeadStageHistory.objects.create(
                        lead=session.lead, from_stage_id=old_stage_id, to_stage=stage, changed_by=self.request.user,
                    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

class LeadDocumentListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadDocumentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['lead']
    queryset = LeadDocument.objects.select_related('lead', 'uploaded_by')

    def perform_create(self, serializer):
        document = serializer.save(uploaded_by=self.request.user)
        _log_activity(document.lead, self.request.user, 'document_added', document.title)


class LeadDocumentDetailView(generics.RetrieveDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadDocumentSerializer
    queryset = LeadDocument.objects.select_related('lead', 'uploaded_by')


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------

class AutomationRuleListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = AutomationRuleSerializer
    queryset = AutomationRule.objects.all()
    pagination_class = None


class AutomationRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = AutomationRuleSerializer
    queryset = AutomationRule.objects.all()


# ---------------------------------------------------------------------------
# Lead Settings + Custom Fields
# ---------------------------------------------------------------------------

class LeadCustomFieldDefinitionListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadCustomFieldDefinitionSerializer
    queryset = LeadCustomFieldDefinition.objects.all()
    pagination_class = None


class LeadCustomFieldDefinitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]
    serializer_class = LeadCustomFieldDefinitionSerializer
    queryset = LeadCustomFieldDefinition.objects.all()


class LeadSettingsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('edit_leads')]

    def get(self, request):
        return Response(LeadSettingsSerializer(LeadSettings.get_solo()).data)

    def patch(self, request):
        serializer = LeadSettingsSerializer(LeadSettings.get_solo(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class LeadAnalyticsOverviewView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasLeadsAccess('view_lead_analytics')]

    RANGE_DAYS = {'30d': 30, '90d': 90, '365d': 365}
    RANK_LIMIT = 10

    def get(self, request):
        from datetime import timedelta

        now = timezone.now()
        active_leads = Lead.objects.filter(is_archived=False)
        total_leads = active_leads.count()
        new_leads_today = active_leads.filter(created_at__date=now.date()).count()
        enrolled_count = active_leads.filter(stage__is_won=True).count()
        lost_count = active_leads.filter(stage__is_lost=True).count()
        retry_count = active_leads.filter(stage__name='Retry').count()
        conversion_rate = round((enrolled_count / total_leads) * 100, 1) if total_leads else 0

        response_times = []
        for lead in active_leads.prefetch_related('activities')[:500]:
            first_contact = lead.activities.exclude(activity_type='created').order_by('created_at').first()
            if first_contact:
                response_times.append((first_contact.created_at - lead.created_at).total_seconds())
        avg_response_time_hours = round((sum(response_times) / len(response_times)) / 3600, 1) if response_times else 0

        admission_times = []
        for history in LeadStageHistory.objects.filter(to_stage__is_won=True).select_related('lead')[:500]:
            admission_times.append((history.created_at - history.lead.created_at).total_seconds())
        avg_admission_time_days = round((sum(admission_times) / len(admission_times)) / 86400, 1) if admission_times else 0

        past_sessions = CounsellingSession.objects.filter(scheduled_at__lt=now)
        past_sessions_count = past_sessions.count()
        demo_attendance_rate = (
            round((past_sessions.exclude(outcome='').count() / past_sessions_count) * 100, 1)
            if past_sessions_count else 0
        )

        counsellor_performance = list(
            AdminMember.objects.filter(assigned_leads__isnull=False)
            .distinct()
            .annotate(
                assigned_count=Count('assigned_leads', filter=Q(assigned_leads__is_archived=False), distinct=True),
                won_count=Count('assigned_leads', filter=Q(assigned_leads__stage__is_won=True), distinct=True),
            )
            .values('id', 'full_name', 'assigned_count', 'won_count')
            .order_by('-assigned_count')[:self.RANK_LIMIT]
        )

        source_performance = []
        for source in LeadSource.objects.all():
            leads_qs = source.leads.filter(is_archived=False)
            total = leads_qs.count()
            won = leads_qs.filter(stage__is_won=True).count()
            source_performance.append({
                'id': source.id,
                'name': source.name,
                'lead_count': total,
                'conversion_rate': round((won / total) * 100, 1) if total else 0,
                'cost_per_lead': round(float(source.campaign_cost) / total, 2) if source.campaign_cost and total else None,
            })

        pipeline_breakdown = [
            {'id': stage.id, 'name': stage.name, 'color': stage.color, 'count': stage.leads.filter(is_archived=False).count()}
            for stage in PipelineStage.objects.all()
        ]

        range_param = request.query_params.get('range', '30d')
        days = self.RANGE_DAYS.get(range_param, 30)
        since = now - timedelta(days=days)
        trend = list(
            active_leads.filter(created_at__gte=since)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        return Response({
            'total_leads': total_leads,
            'new_leads_today': new_leads_today,
            'active_leads': total_leads - enrolled_count - lost_count,
            'enrolled_count': enrolled_count,
            'lost_count': lost_count,
            'retry_count': retry_count,
            'conversion_rate': conversion_rate,
            'avg_response_time_hours': avg_response_time_hours,
            'avg_admission_time_days': avg_admission_time_days,
            'demo_attendance_rate': demo_attendance_rate,
            'counsellor_performance': counsellor_performance,
            'source_performance': source_performance,
            'pipeline_breakdown': pipeline_breakdown,
            'trend': trend,
        })
