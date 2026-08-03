from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import BlogPost
from .serializers import BlogPostSerializer, PublicBlogPostSerializer

BLOG_PERMISSION = 'manage_settings'


class BlogPostListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(BLOG_PERMISSION)]
    serializer_class = BlogPostSerializer
    queryset = BlogPost.objects.all()
    pagination_class = None

    def perform_create(self, serializer):
        is_published = serializer.validated_data.get('is_published', False)
        serializer.save(published_at=timezone.now() if is_published else None)


class BlogPostDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(BLOG_PERMISSION)]
    serializer_class = BlogPostSerializer
    queryset = BlogPost.objects.all()

    def perform_update(self, serializer):
        was_published = serializer.instance.is_published
        is_published = serializer.validated_data.get('is_published', was_published)
        if is_published and not was_published:
            serializer.save(published_at=timezone.now())
        else:
            serializer.save()


class PublicBlogPostListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicBlogPostSerializer
    pagination_class = None

    def get_queryset(self):
        return BlogPost.objects.filter(is_published=True).order_by('-published_at')


class PublicBlogPostDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicBlogPostSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return BlogPost.objects.filter(is_published=True)
