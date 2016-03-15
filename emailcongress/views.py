# python
import json

# django
from django.http import JsonResponse
from django.views.generic import TemplateView, FormView, View
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.core.urlresolvers import reverse

# external
from postmark_inbound import PostmarkInbound
from raven.contrib.django.raven_compat.models import client

# internal
from emailcongress.forms import UserMessageInfoForm, EmailForm, MessageForm
from emailcongress.models import User, Message, Legislator, Token
from emailcongress import emailer
from api.views import MessageViewSet
from services import address_inferrence_service


class AjaxableFormView(object):
    """
    Mixin to add AJAX support to a form.
    Must be used with an object-based FormView (e.g. CreateView)
    """
    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse(form.errors, status=400)
        else:
            return response

    def form_valid(self, form):
        response = super().form_valid(form)
        message = form.process()
        if self.request.is_ajax():
            return JsonResponse({'email': message})
        else:
            messages.info(self.request, message)
            return response


class ConvertTokenMixin(object):

    def dispatch(self, request, *args, **kwargs):
        key = kwargs.get('token', '')
        self.msg, self.umi, self.user = Token.convert_token(key)
        # if token doesn't resolve then redirect to index with error message
        if self.user is None and key != '':
            # TODO create flash message template
            messages.error(request, "Token {0} in provided URL doesn't match any in our records. "
                                    "If you've changed your address then you may be using an outdated token. "
                                    "If you can't locate your most recent token, click here to request an "
                                    "address change and we will send you a new token.".format(key))
            return redirect('index')

        # handles code that needs to be run after successfully resolving token
        if hasattr(self, 'handlers'):
            for handler in self.handlers:
                out = handler(self)
                if out is not None:
                    return out

        return super().dispatch(request, *args, **kwargs)

    def push_post_token_handler(self, handler_func):
        if not hasattr(self, 'handlers'):
            self.handlers = []
        if type(handler_func) is list:
            self.handlers += handler_func
        else:
            self.handlers.append(handler_func)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'msg': self.msg, 'umi': self.umi, 'user': self.user})
        return ctx


class IndexView(AjaxableFormView, FormView):

    template_name = 'www/pages/index.html'
    form_class = EmailForm
    success_url = '/'


class FaqView(TemplateView):

    template_name = 'www/pages/static/faq.html'


class DeveloperInfoView(TemplateView):

    template_name = 'www/pages/static/api.html'


class AutofillAddressView(View):

    def post(self, request, *args, **kwargs):
        address = address_inferrence_service.address_lookup(**(json.loads(request.body.decode('utf-8'))))
        if address is None:
            address = {'error': 'Unable to locate city, state, and zip4.'}
        return JsonResponse(address)


class SignupView(ConvertTokenMixin, FormView):

    template_name = 'www/pages/signup.html'
    form_class = UserMessageInfoForm
    success_url = '/complete'

    def dispatch(self, request, *args, **kwargs):

        def redirect_to_complete(this):
            if this.msg and this.msg.has_legislators:
                return redirect('complete-verify', token=this.msg.token_key)
            if not this.msg and this.user and this.umi and not this.umi.accept_tos:
                self.request.session['email_verify'] = True
                return redirect('complete-verify', token=kwargs.get('token'))

        self.push_post_token_handler(redirect_to_complete)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.user:
            ctx['form'].disable_email_input()
        return ctx

    def get_initial(self):
        if self.user:
            return {'email': self.user.django_user.email}
        return super().get_initial()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.umi:
            kwargs['instance'] = self.umi
            # clear sensitive data from form because we don't want to display that
            for attr in ['street_address', 'street_address2', 'city', 'state', 'phone_number']:
                setattr(kwargs['instance'], attr, '')
            # if POSTing, auto-fill email field and clone instance for new UserMessageInfo
            if self.request.method in ('POST', 'PUT'):
                data = self.request.POST.copy()
                data['email'] = self.user.email
                kwargs['data'] = data
                if self.umi.accept_tos:
                    kwargs['instance'].clone_instance_for_address_update()
        return kwargs

    def form_valid(self, form):
        django_user = form.save()
        if self.msg:
            # updated user info for new user trying to send an email first time
            return redirect('confirm', token=self.msg.token_key)
        elif self.user:
            # updated user info for already existing user
            emailer.NoReply(django_user).address_changed().send()
            self.request.session['address_updated'] = True
            return redirect('complete-verify', token=self.user.token_key)
        else:
            # created new user on initial web signup
            emailer.NoReply(django_user).signup_confirm().send()
            return super().form_valid(form)


class ConfirmRepsView(ConvertTokenMixin, FormView):

    template_name = 'www/pages/confirm.html'
    form_class = MessageForm

    def dispatch(self, request, *args, **kwargs):

        def redirect_to_complete(this):
            if this.msg.has_legislators:
                return redirect(self.get_success_url())

        def set_legislator_buckets(this):
            this.legs_buckets = Legislator.get_leg_buckets_from_emails(this.umi.members_of_congress,
                                                                       this.msg.to_originally)

        self.push_post_token_handler([redirect_to_complete, set_legislator_buckets])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'instance': self.msg, 'legs_buckets': self.legs_buckets})
        return kwargs

    def get_success_url(self):
        return reverse('complete-verify', kwargs={'token': self.msg.token_key})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['legs_buckets'] = self.legs_buckets
        return ctx

    def form_valid(self, form):
        form.complete()
        emailer.NoReply(self.user.django_user).message_queued(form.instance).send()
        return super().form_valid(form)


class CompleteView(ConvertTokenMixin, TemplateView):

    template_name = 'www/pages/complete.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for session_key in ['address_updated', 'email_verify']:
            if self.request.session.get(session_key, False):
                ctx[session_key] = True
                del self.request.session[session_key]
        return ctx

    def get(self, request, *args, **kwargs):
        if self.umi:
            if self.umi.accept_tos is None:
                self.umi.accept_tos = timezone.now()
                self.umi.save()
        return super().get(request, *args, **kwargs)


class PostmarkView(View):

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @csrf_exempt
    def post(self, request, *args, **kwargs):
        try:
            inbound = PostmarkInbound(json=request.body.decode('utf-8'))
            django_user, user, umi = User.get_or_create_user_from_email(inbound.sender()['Email'].lower())

            # get message id for email threading
            if 'Headers' in inbound.source and inbound.headers('Message-ID') is not None:
                msg_id = inbound.headers('Message-ID')
            else:
                msg_id = inbound.message_id()

            if not Message.objects.filter(email_uid=inbound.message_id()).exists():

                new_msg = Message.objects.create(created_at=inbound.send_date(),
                                                 to_originally=[r['Email'].lower() for r in inbound.to()],
                                                 subject=inbound.subject(),
                                                 msgbody=inbound.text_body(),
                                                 email_uid=msg_id,
                                                 user_message_info=umi)

                # first time user or it has been a long time since they've updated their address info
                if umi.must_update_address_info():
                    emailer.NoReply(django_user).email_confirm(new_msg).send()
                    return JsonResponse({'status': 'User must accept tos / update their address info.'})
                else:
                    MessageViewSet.process_inbound_message(django_user, umi, new_msg)
                    return JsonResponse({'status': 'Message queued for processing.'})
            else:
                return JsonResponse({'status': 'Message with provided ID already received.'})
                # TODO robust error handling
        except:
            client.captureException()
            return 'Failure', 500
            # TODO robust error handling
