from __future__ import absolute_import
import os
from celery import Celery
from emailcongress import emailer
from django.conf import settings
import traceback

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'emailcongress.settings.shared')

celery = Celery('emailcongress')
for key, val in settings.CONFIG_DICT['celery'].items():
    setattr(celery.conf, key.upper(), val)


@celery.task(bind=True, max_retries=celery.conf.MAX_RETRIES, default_retry_delay=celery.conf.RETRY_DELAY)
def send_to_phantom_of_the_capitol(self, msg_id=None, msgleg_id=None, force=False):
    """

    @param self:
    @type self:
    @param msg_id:
    @type msg_id:
    @param msgleg_id:
    @type msgleg_id:
    @param force:
    @type force:
    @return:
    @rtype:
    """
    if settings.CONFIG_DICT['email']['submit_to_webform'] or force:
        try:
            from emailcongress.models import Message, MessageLegislator
            if msgleg_id is not None:
                msgleg = MessageLegislator.objects.filter(id=msgleg_id).first()
                msgleg.send()
            elif msg_id is not None:
                msg = Message.objects.get(pk=msg_id)
                msg.send()
                if msg.get_send_status() == 'sent' or self.request.retries >= self.max_retries:
                    emailer.NoReply(msg.user_message_info.user).send_status(msg.to_legislators, msg).send()
                else:
                    raise self.retry(exc=Exception)
        except:
            raise Exception(traceback.format_exc())
            # TODO robust error handling
