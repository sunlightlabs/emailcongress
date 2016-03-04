#!/usr/bin/env python
import os
import sys
from etc import CONFIG_DICT

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emailcongress.settings.%s" % CONFIG_DICT['django']['environment'])
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
