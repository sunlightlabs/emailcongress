import os
import sys
import requests
import uuid
import traceback
import string
import random
import json

from django.core.management.base import BaseCommand, CommandError
from django.core import management
from django.conf import settings

from raven.contrib.django.raven_compat.models import client

from emailcongress.models import *
from emailcongress.utils import construct_link


def reset_database(prompt=True):
    if prompt is True:
        decision = input("This will delete everything in the database. Are you sure you want to do this? [Y,n] ")
        decision2 = input("Are you absolutely sure? This can not be undone ... [Y,n] ") if decision == 'Y' else ''
    else:
        decision = decision2 = 'Y'

    if decision == 'Y' and decision2 == 'Y':
        try:
            print('Running database reset commands...')
            management.call_command('reset_db')
            management.call_command('migrate')
            import_data()
        except:
            print(traceback.format_exc())
    else:
        print("Aborting resetting database.")


def import_data():
    print('Importing congresspeople...')
    management.call_command('daily', 'import_congresspeople', kwargs=[['from_cache', False]])


def create_test_data():
    try:
        from tests.factories import user, user_message_info, message, admin_user

        user1 = user(email='cdunwell@sunlightfoundation.com')
        umi1 = user_message_info(user=user1, info={
            'default': True,
            'prefix': 'Mr.',
            'first_name': 'Clayton',
            'last_name': 'Dunwell',
            'street_address': '2801 Quebec St NW',
            'street_address2': '',
            'city': 'Washington',
            'state': 'DC',
            'zip5': '20008',
            'phone_number': '2025551234'
        })
        msg1_1 = message(umi=umi1)
        msg1_2 = message(umi=umi1)


        # user2 = user(email='ocheng@sunlightfoundation.com')
        # umi2 = user_message_info(user=user2)
        # msg2 = message(umi=umi2)

        for i in list(range(0,100)):
            user(email=(''.join(random.choice(string.ascii_lowercase) for _ in range(10)))+'@example.com')

        admin1 = admin_user()

    except:
        print(traceback.format_exc())


def setup_test_environment():
    reset_database(False)
    create_test_data()


def simulate_postmark_message(from_email, to_emails=None, messageid=None):

    if from_email not in settings.POSTMARK_DEBUG_EMAILS:
        return from_email + " not in admin emails: " + str(settings.POSTMARK_DEBUG_EMAILS)

    messageid = uuid.uuid4().hex if messageid is None else messageid
    if to_emails is None:
        to_emails = [{'Email': 'Rep.Zinke@emailcongress.us'}]
    elif type(to_emails) is str:
        to_emails = [{'Email': to_emails}]
    elif type(to_emails) is list:
        to_emails = [{'Email': te} for te in to_emails]
    else:
        raise Exception('Bad input')

    params = {
        'Subject': 'Thank you!',
        'TextBody': "Thank you for everything that you do!",
        'Date': 'Thu, 5 Apr 2014 16:59:01 +0200',
        'MessageID': messageid,
        "FromFull": {
            "Email": from_email,
            "Name": "John Smith",
        },
        "ToFull": to_emails
    }
    try:
        url = construct_link(settings.PROTOCOL, settings.HOSTNAME, '/postmark/inbound')
        print('Making request to {0}'.format(url))
        req = requests.post(url, data=json.dumps(params))
        print(req.text)
        return req.text
    except:
        client.captureException()

        print('Request to postmark inbound url failed')


def reset_tos(from_email=None):
    try:
        user = User.objects.filter(email=from_email).first()
        user.accept_tos = None
        user.messages().update(status='free')
        # map(lambda msg: setattr(msg, 'status', 'free'), user.messages().all())
    except:
        print('User with email ' + from_email + ' does not exist.')


class Command(BaseCommand):
    help = 'Run admin tasks for development and management.'
    tasks = {
        'reset_database': reset_database,
        'create_test_data': create_test_data,
        'setup_test_environment': setup_test_environment,
        'simulate_postmark_message': simulate_postmark_message,
        'reset_tos': reset_tos
    }

    def add_arguments(self, parser):
        parser.add_argument('task', type=str)
        parser.add_argument('--kwargs', type=lambda kv: kv.split("="), dest='kwargs', nargs='*', default=[])

    def handle(self, **options):
        try:
            task = options.pop('task')
            print('Running {0}'.format(task))
            self.tasks.get(task)(**{item[0]: item[1] for item in options['kwargs']})
        except:
            raise CommandError("Must supply a valid admin task from " + str(self.tasks.keys()))
