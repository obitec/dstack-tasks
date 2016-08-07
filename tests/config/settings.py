from .default import *

DEBUG = True
ALLOWED_HOSTS = ['*']

SITE_ID = os.environ.get("SITE_ID", 1)
SITE_HEADER = 'Example Header'
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
LOGIN_URL = '/admin/login'

# TEMPLATES[0].update({'DIRS': [os.path.join(BASE_DIR, 'templates'), ]})
# TEMPLATES[0]['OPTIONS']['context_processors'].append('config.context_processors.version_tag')

FIXTURE_DIRS = ['config/fixtures']
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
FORMAT_MODULE_PATH = 'config.formats'

LANGUAGES = (
    ('en', 'English'),
    ('af', 'Afrikaans'),
    ('zh-hans', '简体中文'),
)

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(PROJECT_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(PROJECT_DIR, 'media')

MIDDLEWARE_CLASSES += [
    'django.contrib.sites.middleware.CurrentSiteMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    # 'axes.middleware.FailedLoginMiddleware',
]

# Not recommended at moment: https://github.com/etianen/django-reversion/issues/496
# MIDDLEWARE_CLASSES = ['reversion.middleware.RevisionMiddleware', ] + MIDDLEWARE_CLASSES

DJANGO_CONTRIB = [
    'django.contrib.flatpages',
    'django.contrib.sites',
]

EXTENSIONS = [
    'import_export',
    'rest_framework',
    'reversion',
    'guardian',
    # 'debug_toolbar',
]

PROJECT_APPS = [
    'maslow.apps.AdminConfig',
    'example.apps.ExampleConfig',
]

INSTALLED_APPS = INSTALLED_APPS + DJANGO_CONTRIB + EXTENSIONS + PROJECT_APPS


# REST_FRAMEWORK = {
#     # Use Django's standard `django.contrib.auth` permissions,
#     # or allow read-only access for unauthenticated users.
#     'DEFAULT_PERMISSION_CLASSES': [
#         'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
#     ]
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('POSTGRES_DB', 'postgres'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOSTNAME', 'postgres'),
        'PORT': os.environ.get('POSTGRES_PORT_PORT', '5432')
    }
}
