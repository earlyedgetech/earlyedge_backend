
import sys
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Local apps live in apps/<name> and are registered below by their short
# name (e.g. 'authentication', not 'apps.authentication'), so apps/ itself
# needs to be importable.
sys.path.insert(0, str(BASE_DIR / 'apps'))

SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-e_2jv)v80jpzq7z(1v#%&b5qj7$+38a35vjx#d@y@%!8g8yuue',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'admin_security',
    'authentication',
    'blog',
    'certificates',
    'challenges',
    'common',
    'courses',
    'dashboard',
    'instructors',
    'leads',
    'live_classes',
    'materials',
    'placements',
    'promocodes',
    'purchases',
    'revenue',
    'settings_app',
    'students',
    'support',
    'uploads',
    'wishlist',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework
# https://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Early Edge Tech API',
    'DESCRIPTION': 'API for the Early Edge Tech website and admin dashboard.',
    'VERSION': '1.0.0',
}


# Simple JWT
# Tokens are issued/validated by our own custom authentication classes
# (apps/authentication/authentication.py) for two separate audiences —
# Student and AdminMember — so there is no single AUTH_USER_MODEL here.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# CORS
# https://github.com/adamchainz/django-cors-headers

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173',
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True
# Browsers hide all response headers from JS except a small safelist unless
# the server explicitly exposes them — needed so the frontend can read the
# server-generated filename off file-download (export) responses.
CORS_EXPOSE_HEADERS = ['Content-Disposition']


# Email (password reset / verification)
# development.py / production.py select the actual EMAIL_BACKEND.

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@earlyedgetech.com')
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')


# Google OAuth (manual id_token verification)

GOOGLE_OAUTH_CLIENT_ID = config('GOOGLE_OAUTH_CLIENT_ID', default='')


# Celery (background/scheduled tasks — see config/celery.py)
# Requires a running broker (Redis) plus `celery -A config worker` and
# `celery -A config beat` processes; nothing here starts them automatically.

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    'send-cart-abandonment-reminders-daily': {
        'task': 'purchases.tasks.send_cart_abandonment_reminders',
        'schedule': config('CART_REMINDER_SCHEDULE_SECONDS', default=86400, cast=int),
    },
    'send-live-class-reminders': {
        'task': 'live_classes.tasks.send_live_class_reminders',
        'schedule': config('LIVE_CLASS_REMINDER_SCHEDULE_SECONDS', default=300, cast=int),
    },
    'send-lead-followup-digest-daily': {
        'task': 'leads.tasks.send_followup_digest',
        'schedule': config('LEAD_FOLLOWUP_DIGEST_SCHEDULE_SECONDS', default=86400, cast=int),
    },
    'run-lead-scheduled-automations-daily': {
        'task': 'leads.tasks.run_scheduled_automations',
        'schedule': config('LEAD_AUTOMATIONS_SCHEDULE_SECONDS', default=86400, cast=int),
    },
}
