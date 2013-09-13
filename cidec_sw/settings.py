# Django settings for cidec_sw project.
import djcelery
djcelery.setup_loader()
import os
CELERY_RESULT_BACKEND = "amqp"

BROKER_URL = 'amqp://guest:guest@localhost:5672//'

CELERY_IMPORTS = ('tareas', 'cidec_sw.tests')
CELERY_TASK_TIME_LIMIT = 86400

PROJECT_PATH = os.path.abspath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), os.path.pardir))
SERVER_URL = "http://auditem.mx"
DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'test': {
        'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'satest_cidec',                      # Or path to database file if using sqlite3.
        'USER': 'satest_cidec',                      # Not used with sqlite3.
        'PASSWORD': '5MnT)HXnm_pT',                  # Not used with sqlite3.
        'HOST': 'audiwime.wimelabs.com',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    },
    "default": {
        'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'satest_cidec',                      # Or path to database file if using sqlite3.
        'USER': 'satest_cidec',                      # Not used with sqlite3.
        'PASSWORD': '5MnT)HXnm_pT',                  # Not used with sqlite3.
        'HOST': 'auditem.mx',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    },
    'local': {
        'ENGINE': 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'satest_cidec',                      # Or path to database file if using sqlite3.
        'USER': 'root',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}
DATABASE_ENGINE = 'django.db.backends.mysql'
# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Mexico_City'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'es-mx'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(PROJECT_PATH, 'templates/static/media/')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/static/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
#STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PROJECT_PATH, 'templates/static/'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'tr&amp;!=v*6v--y&amp;8bg20v4+%m3u9aj6ekbv-(ei$jst90h9tdz_c'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)
TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'cidec_sw.context_processors.extra_template_vars'
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'cidec_sw.middleware.timezones.TimezoneMiddleware',
    'cidec_sw.middleware.timezones.YearsMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware'
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'cidec_sw.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'cidec_sw.wsgi.application'

TEMPLATE_DIRS = (os.path.join(PROJECT_PATH, 'templates'))#'/Users/wime/Dev/wime_dev/cidec_sw/templates',)

INSTALLED_APPS = (
    #'grappelli',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    #'django.contrib.admindocs',
    'location',
    'c_center',
    'rbac',
    'electric_rates',
    'south',
    'data_warehouse',
    'data_warehouse_extended',
    'reports',
    'alarms',
    'django_tables2',
    'plupload',
    'djcelery',
    'tareas',
    #'debug_toolbar'
)


def show_toolbar(request):
    return True
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': show_toolbar,
    'INTERCEPT_REDIRECTS': False
}

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },

    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },

        'simple': {
            'format': '%(levelname)s %(message)s'
        },

    },

    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },

        'file_data_warehouse': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': PROJECT_PATH + '/log_data_warehouse.log',
            'formatter': 'verbose'
        },

        'file_reports': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': PROJECT_PATH + '/log_reports.log',
            'formatter': 'verbose'
        },

        'console':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },

    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },

        'data_warehouse': {
            'handlers': ['file_data_warehouse', 'console'],
            'level': 'INFO',
            'propagate': True,
        },

        'reports': {
            'handlers': ['file_reports', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}

GRAPPELLI_ADMIN_TITLE = 'CIDEC'
ADMIN_MEDIA_PREFIX = ""

"""
SESSION_ENGINE = 'redis_sessions.session'
SESSION_REDIS_HOST = 'localhost'
SESSION_REDIS_PORT = 6379
SESSION_REDIS_DB = 0

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': 'localhost:6379',
        'OPTIONS': {
            'DB': 1,
        },
    },
}
"""
