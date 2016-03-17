from django.conf import settings
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse

from postmark import PMMail

from emailcongress import utils


class NoReply(PMMail):

    HTML_BODY_TEMPLATE_DIR = 'emails/html_body/'
    TEXT_BODY_TEMPLATE_DIR = 'emails/text_body/'

    def __init__(self, django_user, **kwargs):
        super().__init__(**kwargs)
        self.user = django_user.user
        self.to = django_user.email
        self.ctx = {'user': self.user,
                    'verification_link': self.user.verification_link,
                    'faq_link': utils.construct_link(settings.PROTOCOL, settings.HOSTNAME, reverse('faq'))}

    def send(self, test=False):

        if not settings.DEBUG or (settings.DEBUG and self.to in settings.POSTMARK_DEBUG_EMAILS):
            print('Sending live email to ' + self.to)
            return super().send(test=test)
        else:
            print('Debug mode and/or {0} not in list of admin emails'.format(self.to))
            return super().send(test=True)

            # TODO robust error handling

    def _set_custom_headers_from_msg(self, msg):
        """
        Sets custom headers from message object

        @param msg: an instance of a message
        @type msg: emailcongress.models.Message
        @return: the instance of NoReply
        @rtype: NoReply
        """
        self._set_custom_headers({'In-Reply-To': msg.email_uid, 'References': msg.email_uid})
        return self

    #  ___ __  __   _   ___ _      __  __ ___ _____ _  _  ___  ___  ___  #
    # | __|  \/  | /_\ |_ _| |    |  \/  | __|_   _| || |/ _ \|   \/ __| #
    # | _|| |\/| |/ _ \ | || |__  | |\/| | _|  | | | __ | (_) | |) \__ \ #
    # |___|_|  |_/_/ \_\___|____| |_|  |_|___| |_| |_||_|\___/|___/|___/ #

    def signup_confirm(self):
        """
        If user signs up through index page then they receive a confirmation email
        with their change address link to verify they are indeed the owner of the email.
        """
        self.subject = "Confirm your Email Congress account."
        self.html_body = render_to_string('emails/html_body/signup_confirm.html', context=self.ctx)
        return self

    def address_change_request(self):
        """
        User requests to change their address
        """
        self.subject = "You've requested to change your address information on Email Congress."
        self.html_body = render_to_string("emails/html_body/address_change_request.html", context=self.ctx)
        return self

    def remind_reps(self):
        self.ctx['members_of_congress'] = self.user.members_of_congress

        self.subject = "Reminder of your members of Congress"
        self.html_body = render_to_string('emails/html_body/remind_reps.html', context=self.ctx)
        return self

    def email_confirm(self, msg):
        """
        Handles the case of a first time user or a user who needs to renew their contact information.

        @param msg: the message object
        @type msg: emailcongress.models.Message
        """
        self.ctx['verification_link'] = msg.verification_link
        self.ctx['hide_address_update_link'] = True

        self.subject = 'Re: ' + msg.subject
        self.html_body = render_to_string('emails/html_body/email_confirm.html', context=self.ctx)
        self._set_custom_headers_from_msg(msg)
        return self

    def signup_success(self):
        """

        @param msg: the message object
        @type msg: emailcongress.models.Message
        """
        self.ctx['members_of_congress'] = self.user.members_of_congress

        self.subject = 'You are successfully signed up for Email Congress!'
        self.html_body = render_to_string('emails/html_body/signup_success.html', context=self.ctx)
        return self

    def reconfirm_info(self, msg):
        """

        @param msg: the message object
        @type msg: emailcongress.models.Message
        @return:
        @rtype:
        """

        self.subject = "Complete your email to Congress"
        self.html_body = render_to_string("emails/revalidate_user.html", context=self.ctx)
        self._set_custom_headers_from_msg(msg)
        return self

    def over_rate_limit(self, msg):
        self.ctx['msg'] = msg

        self.subject = "You've sent too many emails recently."
        self.html_body = render_to_string("emails/over_rate_limit.html", context=self.ctx)
        self._set_custom_headers_from_msg(msg)
        return self

    def message_queued(self, msg):
        self.ctx['legislators'] = msg.get_legislators()

        self.subject = "Your email is now on its way!"
        self.html_body = render_to_string("emails/html_body/message_queued.html", context=self.ctx)
        self._set_custom_headers_from_msg(msg)
        return self

    def message_undeliverable(self, leg_buckets, msg):

        self.ctx['leg_buckets'] = leg_buckets

        self.subject = "Your message to congress is unable to be delivered."
        self.html_body = render_to_string("emails/html_body/message_undeliverable.html", context=self.ctx)
        self._set_custom_headers_from_msg(msg)
        return self

    def message_receipt(self, legs, msg):
        """
        Handles the follow-up email for every time a user sends an email message.

        @param legs:
        @type legs:
        @param msg:
        @type msg:
        """

        rls = msg.status

        subject = {
            None: 'Your message to your representatives will be sent.',
            'free': 'Your message to your representatives is schedule to be sent.',
            'captcha': "You must solve a captcha to complete your message to congress",
            'g_captcha': 'You must complete your message to Congress.',
            'block': 'Unable to send your message to congress at this time.'
        }.get(rls)

        self.subject = subject
        self.html_body = render_to_string("emails/message_receipt.html",
                                          context={'legislators': legs,
                                                   'msg': msg,
                                                   'user': self.user,
                                                   'rls': rls})
        self._set_custom_headers_from_msg(msg)
        return self

    def send_status(self, msg_legs, msg):
        """
        Handles the case where phantom of the capitol is unable to send a message to a particular
        legislator. Notifies the user of such and includes the contact form URL in the body.

        @param msg_legs:
        @type msg_legs:
        @param msg:
        @type msg:
        @return: a python representation of a postmark object
        @rtype: PMMail
        """
        send_statuses = {'sent': [], 'unsent': []}
        for ml in msg_legs:
            send_statuses['sent' if ml.sent else 'unsent'].append(ml.legislator)

        if send_statuses['unsent']:
            subject = 'There were errors processing your recent message to congress.'
        else:
            subject = 'Your recent message to congress has successfully sent.'

        self.ctx['statuses'] = send_statuses

        self.subject = subject
        self.html_body = render_to_string("emails/html_body/send_status.html", context=self.ctx)
        self._set_custom_headers_from_msg(msg)
        return self

    def successfully_reset_token(self):
        """
        Handles the case of notifying a user when they've changed their address information.

        """

        self.subject = 'Your Email Congress token has been successfully reset.'
        self.html_body = render_to_string('emails/successfully_reset_token.html',
                                          context={'user': self.user, 'link': self.user.token.link()})

    def address_changed(self):
        """
        Handles the case of notifying a user when they've changed their address information.
        """
        self.ctx['members_of_congress'] = self.user.members_of_congress

        self.subject = 'Your Email Congress contact information has changed.'
        self.html_body = render_to_string('emails/html_body/address_changed.html', context=self.ctx)
        return self

    def custom_email(self, subject, html_template, text_template, context, custom_headers=None):
        """
        Create a custom email that doesn't exist in the predefined emails above.

        @param subject: the subject of the email
        @type subject: str
        @param html_template: path/to/template to use for html body
        @type html_template: str
        @param text_template: path/to/template to use for plain text body
        @type text_template: str
        @param context: dictionary of values to supply to template
        @type context: dict
        @param custom_headers: custom headers to attach to this email
        @type custom_headers: dict
        @return: postmark email object
        @rtype: PMMail
        """
        self.ctx.update(context)

        self.subject = subject
        self.html_body = render_to_string(html_template, context=self.ctx)
        self.text_body = render_to_string(text_template, context=self.ctx)

        if custom_headers is not None:
            self._set_custom_headers(custom_headers)

        return self
