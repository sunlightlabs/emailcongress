"""
WSGI config for emailcongress project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/howto/deployment/wsgi/
"""

import os
import yaml

from django.core.wsgi import get_wsgi_application

ETC_DIR_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DICT = yaml.load(open(os.path.join(ETC_DIR_PATH, 'etc/config.yaml'), 'r'))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emailcongress.settings.%s" % CONFIG_DICT['django']['settings'])

application = get_wsgi_application()
