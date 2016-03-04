"""
WSGI config for emailcongress project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/howto/deployment/wsgi/
"""

import os
from etc import CONFIG_DICT
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emailcongress.settings.%s" % CONFIG_DICT['django']['environment'])

application = get_wsgi_application()
