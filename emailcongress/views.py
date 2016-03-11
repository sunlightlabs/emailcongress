import json
import traceback
import datetime

from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.views.generic import TemplateView, FormView, View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from postmark_inbound import PostmarkInbound

from emailcongress.forms import UserMessageInfoForm, EmailForm
from emailcongress.models import User, Message, Legislator, Token, DjangoUser
from emailcongress import emailer
from api.views import MessageViewSet
from services import address_inferrence_service


class AjaxableFormView(FormView):
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
        # We make sure to call the parent's form_valid() method because
        # it might do some processing (in the case of CreateView, it will
        # call form.save() for example).
        django_user = DjangoUser.objects.get(email=form.cleaned_data['email'])
        if django_user:
            if form.cleaned_data['submit_type'] == 'update_address':
                emailer.NoReply(django_user).address_change_request().send()
            elif form.cleaned_data['submit_type'] == 'remind_reps':
                emailer.NoReply(django_user).remind_reps().send()
            else:
                return self.failure_msg()
        else:
            return 'An error occurred.'

        response = super().form_valid(form)
        if self.request.is_ajax():
            data = {
                'pk': self.object.pk,
            }
            return JsonResponse(data)
        else:
            return response


class AbstractView(View):
    pass


class IndexView(AbstractView, AjaxableFormView):

    template_name = 'www/pages/index.html'
    form_class = EmailForm
    success_url = ''


class FaqView(AbstractView, TemplateView):

    template_name = 'www/pages/static/faq.html'


class AutofillAddressView(AbstractView):

    def post(self, request, *args, **kwargs):
        address = address_inferrence_service.address_lookup(**(json.loads(request.body.decode('utf-8'))))
        if address is None:
            address = {'error': 'Unable to locate city, state, and zip4.'}
        return JsonResponse(address)


class SignupView(AbstractView, FormView):

    template_name = 'www/pages/signup.html'
    form_class = UserMessageInfoForm
    success_url = '/complete'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.user:
            ctx['form'].disable_email_input()
        return ctx

    def get_initial(self):
        if self.user:
            return {'email': self.user.django_user.email}
        return super().get_initial()

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        kwargs = self.get_form_kwargs()
        kwargs['instance'] = self.umi if self.umi else None
        return form_class(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        self.msg, self.umi, self.user = Token.convert_token(kwargs.get('token', ''))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.msg:
            pass
            # TODO modify form for signup through first message
        elif self.user and self.umi:
            if not self.umi.accept_tos:
                return redirect('complete-verify', token=kwargs.get('token'))
            else:
                pass # TODO handleken updating user address
        else:
            # TODO handle way to notify user that token is unknown
            return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.user:
            return super().post(request, *args, **kwargs)
        else:
            form = self.get_form()
            if form.is_valid_with_original_email(self.user.email):
                return self.form_valid(form)
            else:
                return self.form_invalid(form)

    def form_valid(self, form):
        django_user = form.save()
        if self.msg:
            pass
        elif self.user:
            pass
        else:
            emailer.NoReply(django_user).signup_confirm().send()
            return super().form_valid(form)


class ConfirmRepsView(AbstractView):
    pass


class CompleteView(AbstractView, TemplateView):

    template_name = 'www/pages/complete.html'

    def dispatch(self, request, *args, **kwargs):
        self.msg, self.umi, self.user = Token.convert_token(kwargs.get('token', ''))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'msg': self.msg, 'umi': self.umi, 'user': self.user})
        return ctx

    def get(self, request, *args, **kwargs):
        if self.umi:
            if self.umi.accept_tos is None:
                self.umi.accept_tos = datetime.datetime.now()
                self.umi.save()
        return super().get(request, *args, **kwargs)


class PostmarkView(AbstractView):

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @csrf_exempt
    def post(self, request, *args, **kwargs):
        try:
            inbound = PostmarkInbound(json=request.body.decode('utf-8'))
            django_user, user, umi = User.create_new_user(inbound.sender()['Email'].lower())

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
            return 'Failure', 500
            # TODO robust error handling
