import json
import traceback

from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.views.generic import TemplateView, FormView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from postmark_inbound import PostmarkInbound

from emailcongress.models import User, Message, Legislator
from emailcongress import emailer
from api.views import MessageViewSet
from emailcongress.forms import UserMessageInfoForm

from services import address_inferrence_service


class AbstractView(TemplateView):

    pass


class IndexView(AbstractView):

    template_name = 'www/pages/index.html'


class FaqView(AbstractView):

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

    def form_valid(self, form):
        django_user = form.save()
        emailer.NoReply(django_user).signup_confirm().send()

        redirect = super().form_valid(form)
        # This is to allow new users to see the complete view shortly after signup.
        # People can manually set this cookie to see the complete view but there's nothing
        # to gain from seeing that page. New account creation is handled through this class and method.
        redirect.set_cookie('signup', True, max_age=300)
        return redirect

        """
        args = {'func_name': 'update_user_address'}
        if context['user'] is not None: args['token'] = token
        form = forms.RegistrationForm(request.form, app_router_path(**args))

        context.update({
            'form': form,
            'verification_token': token,
        })

        if request.method == 'POST':

            if request.form.get('signup', False):
                status, result = form.signup()
                if status:
                    emailer.NoReply.signup_confirm(status).send()
                    context['signup'] = result
            else:
                error = form.validate_and_save_to_db(context['user'], msg=context['msg'])
                if type(error) is str:
                    if error == 'district_error': context['district_error'] = True
                else:
                    if context['msg'] is None:
                        token = context['user'].token.reset()
                        emailer.NoReply.address_changed(context['user']).send()
                    else:
                        emailer.NoReply.signup_success(context['user'], context['msg']).send()
                return redirect(url_for_with_prefix('app_router.confirm_reps', token=token))

        return render_template_wctx("pages/update_user_address.html", context=context)
        """


class ConfirmRepsView(AbstractView):
    pass


class CompleteView(AbstractView):

    template_name = 'www/pages/complete.html'

    def get(self, request, *args, **kwargs):
        if self.request.COOKIES.get('signup', False):
            return super().get(request, *args, **kwargs)
        else:
            return HttpResponseRedirect('/')


class PostmarkView(AbstractView):

    def post(self, request, *args, **kwargs):

        try:
            # parse inbound postmark JSON
            inbound = PostmarkInbound(json=request.body)

            user = User.objects.create(email=inbound.sender()['Email'].lower())
            umi = user.default_info

            # get message id for email threading
            if 'Headers' in inbound.source and inbound.headers('Message-ID') is not None:
                msg_id = inbound.headers('Message-ID')
            else:
                msg_id = inbound.message_id()

            # check if message exists already first
            if Message.objects.filter(email_uid=inbound.message_id()).exists():

                new_msg = Message.objects.create(created_at=inbound.send_date(),
                                                 to_originally=[r['Email'].lower() for r in inbound.to()],
                                                 subject=inbound.subject(),
                                                 msgbody=inbound.text_body(),
                                                 email_uid=msg_id,
                                                 user_message_info=umi)

                # first time user or it has been a long time since they've updated their address info
                if umi.should_update_address_info():
                    emailer.NoReply(user).validate_user(new_msg).send()
                    return JsonResponse({'status': 'User must accept tos / update their address info.'})
                else:
                    MessageViewSet.process_inbound_message(user, umi, new_msg, send_email=True)
                    return JsonResponse({'status': 'Message queued for processing.'})
            else:
                return JsonResponse({'status': 'Message with provided ID already received.'})
        except:
            print(traceback.format_exc())
            return "Unable to parse postmark message.", 500
