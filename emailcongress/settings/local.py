from emailcongress.settings.shared import *

DEBUG = True

STATICFILES_STORAGE = 'emailcongress.settings.MyStaticFilesStorage'

STATICFILES_DIRS += [os.path.join(BASE_DIR, "staticfiles"), ]

PROTOCOL = CONFIG_DICT.get('protocol', 'http')

if DEBUG:
    try:
        import debug_toolbar
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE_CLASSES += ['debug_toolbar.middleware.DebugToolbarMiddleware']

        def show_toolbar(request):
            return True

        DEBUG_TOOLBAR_CONFIG = {
            "SHOW_TOOLBAR_CALLBACK": show_toolbar,
        }

        # TODO figure out memcache debug panel

    except ImportError:
        pass
    try:
        import uwsgi
        from uwsgidecorators import timer
        from django.utils import autoreload

        # this simulates autoreload like manage.py runserver for uwsgi
        @timer(2)
        def change_code_graceful_reload(sig):
            if autoreload.code_changed():
                uwsgi.reload()
    except:
        pass
