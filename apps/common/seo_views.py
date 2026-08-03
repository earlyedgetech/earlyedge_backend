"""Dynamic robots.txt / sitemap.xml for the public marketing site — always
reflects real published content (courses, instructors, blog posts), unlike
a static file. Mounted at the site root in config/urls.py (NOT under /api/)
since search engines expect them at https://<domain>/sitemap.xml — the
production reverse proxy must route these two top-level paths to this
Django app, same as it already must for /api/."""

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET

STATIC_PAGES = [
    ('', '1.0', 'daily'),
    ('courses', '0.9', 'daily'),
    ('pricing', '0.8', 'weekly'),
    ('instructors', '0.7', 'weekly'),
    ('blogs', '0.7', 'daily'),
    ('faq', '0.5', 'monthly'),
    ('contact', '0.5', 'monthly'),
    ('daily-challenges', '0.6', 'weekly'),
    ('become-instructor', '0.4', 'monthly'),
]


@require_GET
def robots_txt(request):
    base_url = settings.FRONTEND_URL.rstrip('/')
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin-dashboard/',
        'Disallow: /checkout',
        'Disallow: /cart',
        'Disallow: /my-courses',
        'Disallow: /settings',
        '',
        f'Sitemap: {base_url}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@require_GET
def sitemap_xml(request):
    from blog.models import BlogPost
    from courses.models import Course
    from instructors.models import Instructor

    base_url = settings.FRONTEND_URL.rstrip('/')
    urls = []

    for path, priority, changefreq in STATIC_PAGES:
        urls.append((f'{base_url}/{path}', None, priority, changefreq))

    courses = Course.objects.filter(status='published', visibility='public').only('slug', 'updated_at')
    for course in courses:
        urls.append((f'{base_url}/courses/{course.slug}', course.updated_at, '0.9', 'weekly'))

    instructors = Instructor.objects.filter(admin_verified=True).only('id', 'updated_at')
    for instructor in instructors:
        urls.append((f'{base_url}/instructors/{instructor.id}', instructor.updated_at, '0.6', 'monthly'))

    posts = BlogPost.objects.filter(is_published=True).only('slug', 'updated_at')
    for post in posts:
        urls.append((f'{base_url}/blogs/{post.slug}', post.updated_at, '0.6', 'weekly'))

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, priority, changefreq in urls:
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{loc}</loc>')
        if lastmod:
            xml_parts.append(f'    <lastmod>{lastmod.date().isoformat()}</lastmod>')
        xml_parts.append(f'    <changefreq>{changefreq}</changefreq>')
        xml_parts.append(f'    <priority>{priority}</priority>')
        xml_parts.append('  </url>')
    xml_parts.append('</urlset>')

    return HttpResponse('\n'.join(xml_parts), content_type='application/xml')
