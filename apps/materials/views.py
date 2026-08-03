from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from live_classes.models import Batch
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MaterialCategory, MaterialFile, MaterialShare, MaterialSubcategory
from .serializers import (
    MaterialCategorySerializer,
    MaterialFileSerializer,
    MaterialShareSerializer,
    MaterialStudentFileSerializer,
    MaterialSubcategorySerializer,
)


class IsMaterialsManager(HasDashboardPermission):
    def __init__(self):
        super().__init__('manage_materials')


# ---------------------------------------------------------------------------
# Dashboard (RBAC)
# ---------------------------------------------------------------------------

class MaterialCategoryListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]
    serializer_class = MaterialCategorySerializer
    queryset = MaterialCategory.objects.prefetch_related('subcategories__files')
    pagination_class = None


class MaterialCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]
    serializer_class = MaterialCategorySerializer
    queryset = MaterialCategory.objects.prefetch_related('subcategories__files')


class MaterialSubcategoryListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]
    serializer_class = MaterialSubcategorySerializer
    pagination_class = None

    def get_queryset(self):
        queryset = MaterialSubcategory.objects.select_related('category').prefetch_related('files')
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset


class MaterialSubcategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]
    serializer_class = MaterialSubcategorySerializer
    queryset = MaterialSubcategory.objects.select_related('category')


class MaterialFileListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]
    serializer_class = MaterialFileSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = MaterialFile.objects.select_related('subcategory', 'uploaded_by')
        subcategory_id = self.request.query_params.get('subcategory')
        if subcategory_id:
            queryset = queryset.filter(subcategory_id=subcategory_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class MaterialFileDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]
    serializer_class = MaterialFileSerializer
    queryset = MaterialFile.objects.select_related('subcategory', 'uploaded_by')


class MaterialFileShareView(APIView):
    """Share (or view/revoke the share of) a material file with one or more
    live-class batches — every student registered in a shared batch gets
    access to the file via MaterialsSharedListView."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsMaterialsManager]

    def get_object(self, pk):
        try:
            return MaterialFile.objects.get(pk=pk)
        except MaterialFile.DoesNotExist:
            raise NotFound('Material file not found.')

    def get(self, request, pk):
        material_file = self.get_object(pk)
        shares = MaterialShare.objects.filter(material_file=material_file).select_related('batch__course')
        return Response(MaterialShareSerializer(shares, many=True).data)

    def post(self, request, pk):
        material_file = self.get_object(pk)
        batch_ids = request.data.get('batch_ids', [])
        if not batch_ids:
            raise ValidationError({'batch_ids': 'At least one batch id is required.'})

        batches = Batch.objects.filter(id__in=batch_ids)
        created = []
        for batch in batches:
            share, _ = MaterialShare.objects.get_or_create(
                material_file=material_file, batch=batch, defaults={'shared_by': request.user},
            )
            created.append(share)

        return Response(MaterialShareSerializer(created, many=True).data, status=201)

    def delete(self, request, pk):
        material_file = self.get_object(pk)
        batch_id = request.query_params.get('batch')
        if not batch_id:
            raise ValidationError({'batch': 'A batch id query param is required to unshare.'})
        MaterialShare.objects.filter(material_file=material_file, batch_id=batch_id).delete()
        return Response(status=204)


# ---------------------------------------------------------------------------
# Student-facing
# ---------------------------------------------------------------------------

class MaterialsSharedListView(generics.ListAPIView):
    """Files shared to any batch the logged-in student is registered in."""

    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = MaterialStudentFileSerializer

    def get_queryset(self):
        return (
            MaterialFile.objects.select_related('subcategory__category')
            .filter(shares__batch__registrations__student=self.request.user)
            .distinct()
        )
