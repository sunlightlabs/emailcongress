from emailcongress.settings.shared import *

DEBUG = True

STATICFILES_STORAGE = 'emailcongress.settings.MyStaticFilesStorage'

STATICFILES_DIRS += [os.path.join(BASE_DIR, "staticfiles"), ]

PROTOCOL = CONFIG_DICT.get('protocol', 'http')