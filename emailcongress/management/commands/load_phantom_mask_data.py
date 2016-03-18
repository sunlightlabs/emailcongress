from django.core.management.base import BaseCommand, CommandError
import json
from django.conf import settings
import os
from emailcongress import models
import traceback
from django.utils import timezone
from datetime import datetime
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('datafile', type=str)

    def handle(self, **options):
        try:
            user_dict = {}
            umi_dict = {}
            msg_dict = {}
            msgleg_dict = {}
            data = json.load(open(os.path.join(settings.BASE_DIR, options.get('datafile')), 'r'))

            for i in range(0, len(data['User'])):
                _user = json.loads(data['User'][i])
                django_user, c = models.DjangoUser.objects.get_or_create(username=_user['email'][0:30], email=_user['email'])
                user, created = models.User.objects.get_or_create(django_user=django_user)
                user_dict[_user['id']] = user
                data['User'][i] = _user

            for i in range(0, len(data['UserMessageInfo'])):
                _umi = json.loads(data['UserMessageInfo'][i])
                try:
                    _umi_id = _umi.pop('id')
                    _umi['user'] = user_dict[_umi.pop('user_id')]
                except:
                    print(_umi)
                    continue
                _at = timezone.make_aware(datetime.strptime(_umi['created_at'], "%Y-%m-%dT%H:%M:%S.%f"))
                _umi.update({'created_at': _at, 'updated_at': _at})
                umi = models.UserMessageInfo(**_umi)
                if _umi['accept_tos']:
                    umi.accept_tos = timezone.make_aware(datetime.strptime(_umi['accept_tos'], "%Y-%m-%dT%H:%M:%S.%f"))
                else:
                    umi.accept_tos = None
                if not _umi['district']:
                    umi.district = None
                umi.save()
                umi_dict[_umi_id] = umi

            for i in range(0, len(data['Message'])):
                _msg = json.loads(data['Message'][i])
                try:
                    _msg_id = _msg.pop('id')
                    _msg['user_message_info'] = umi_dict[_msg.pop('user_message_info_id')]
                except:
                    print(_msg)
                    continue
                _at = timezone.make_aware(datetime.strptime(_msg['created_at'], "%Y-%m-%dT%H:%M:%S"))
                _msg.update({'created_at': _at, 'updated_at': _at})
                msg = models.Message(**_msg)
                msg.save()
                msg_dict[_msg_id] = msg

            for i in range(0, len(data['MessageLegislator'])):
                _msgleg = json.loads(data['MessageLegislator'][i])
                try:
                    _msgleg_id = _msgleg.pop('id')
                    _msgleg['message'] = msg_dict[_msgleg.pop('message_id')]
                    _msgleg['legislator'] = models.Legislator.objects.filter(bioguide_id=_msgleg.pop('legislator_id')).first()
                    del _msgleg['topic_id']
                except:
                    print(_msgleg)
                    continue
                msgleg = models.MessageLegislator(**_msgleg)
                if not _msgleg['sent']:
                    msgleg.sent = None
                msgleg.save()
                msgleg_dict[_msgleg_id] = msgleg

            for i in range(0, len(data['Token'])):
                _token = json.loads(data['Token'][i])
                model = ContentType.objects.get_for_model(model=getattr(models, _token['item_table'].capitalize()))
                models.Token.objects.get_or_create(key=_token['token'], object_id=_token['item_id'], content_type=model)

            print("Successfully imported JSON data from phantom mask database.")
        except:
            print(traceback.format_exc())
