
from common.seo_views import robots_txt, sitemap_xml
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', robots_txt, name='robots-txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap-xml'),
    path('api/auth/', include('authentication.urls')),
    path('api/admin-security/', include('admin_security.urls')),
    path('api/support/', include('support.urls')),
    path('api/promocodes/', include('promocodes.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/instructors/', include('instructors.urls')),
    path('api/students/', include('students.urls')),
    path('api/purchases/', include('purchases.urls')),
    path('api/wishlist/', include('wishlist.urls')),
    path('api/certificates/', include('certificates.urls')),
    path('api/live-classes/', include('live_classes.urls')),
    path('api/leads/', include('leads.urls')),
    path('api/placements/', include('placements.urls')),
    path('api/challenges/', include('challenges.urls')),
    path('api/revenue/', include('revenue.urls')),
    path('api/settings/', include('settings_app.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    path('api/uploads/', include('uploads.urls')),
    path('api/materials/', include('materials.urls')),
    path('api/blog/', include('blog.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
