import os
import dj_database_url
import raven
import logging
from etc import CONFIG_DICT

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOSTNAME = CONFIG_DICT['hostname']
PROTOCOL = CONFIG_DICT.get('protocol', 'http')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = CONFIG_DICT['django'].get('secret-key', 'not-so-secret')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    # django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # extra
    'django_extensions',
    'widget_tweaks',
    'storages',
    'rest_framework',
    'raven.contrib.django.raven_compat',

    # ours
    'emailcongress',
    'api',
]

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211',
    }
}

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'emailcongress.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, "emailcongress/templates"),
            os.path.join(BASE_DIR, "emailcongress/static/images"),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        },
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

WSGI_APPLICATION = 'emailcongress.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases
# https://github.com/kennethreitz/dj-database-url
# dj_database_url allows the database to be specified in the environmental variable DATABASE_URL as a string
DATABASES = {'default': dj_database_url.config(default=CONFIG_DICT['django']['database_uri'])}

# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators
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
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        }
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.getenv('ERROR_LOG_FILE', os.path.join(BASE_DIR, 'local.log')),
            'formatter': 'verbose'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django': {
            'level': 'ERROR',
            'handlers': ['file'],
            'propagate': False
        },
        'raven': {
            'level': 'ERROR',
            'handlers': ['sentry'],
            'propagate': False,
        },
    }
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_FINDERS_IGNORE = [
    'sass',
    'js_',
    'css_'
]

STATICFILES_FINDERS = [
    'emailcongress.settings.AppDirectoriesFinderIgnore',
    'emailcongress.settings.FileSystemFinderIgnore'
]

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "emailcongress/static"),
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated'
    ],

    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authenticators.TokenAuthentication',
    ]
}

EMAIL_BACKEND = 'postmark.django_backend.EmailBackend'

POSTMARK_API_KEY = CONFIG_DICT['api_keys']['postmark']
POSTMARK_SENDER = CONFIG_DICT['email']['no_reply']
POSTMARK_TEST_MODE = True
POSTMARK_TRACK_OPENS = True
POSTMARK_DEBUG_EMAILS = CONFIG_DICT['email']['approved_debug_emails']

DAYS_TOS_VALID = CONFIG_DICT['misc']['tos_days_valid']

if CONFIG_DICT['raven']['dsn']:

    RAVEN_CONFIG = {
        'dsn': CONFIG_DICT['raven']['dsn'],
        'release': raven.fetch_git_sha(BASE_DIR),
        'CELERY_LOGLEVEL': logging.ERROR,
    }

    LOGGING['handlers']['sentry'] = {
        'level': 'ERROR',
        'class': 'raven.contrib.django.handlers.SentryHandler',
        'formatter': 'verbose'
    }

    LOGGING['root'] = {
        'level': 'WARNING',
        'handlers': ['sentry']
    }

    LOGGING['loggers']['raven'] = {
        'level': 'ERROR',
        'handlers': ['sentry'],
        'propagate': False,
    }
