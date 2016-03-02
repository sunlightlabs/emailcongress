#!/usr/bin/env python
import os
import sys
import yaml

if __name__ == "__main__":
    ETC_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
    CONFIG_DICT = yaml.load(open(os.path.join(ETC_DIR_PATH, 'etc/config.yaml'), 'r'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emailcongress.settings.%s" % CONFIG_DICT['django']['settings'])

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
