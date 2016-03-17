from rest_framework import viewsets
from emailcongress import models
from api.serializers import UserSerializer, LegislatorSerializer, MessageSerializer
from rest_framework import generics
import abc
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import detail_route, list_route
from django.core.exceptions import FieldError
from rest_framework.views import exception_handler
from rest_framework import exceptions
from datetime import datetime
from emailcongress import emailer
import traceback


class GenericQueryModelViewSet(viewsets.ModelViewSet):
    __metaclass__ = abc.ABCMeta

    def get_queryset(self):
        """
        Handles querying with GET parameters in an abstract way.

        @return: filtered queryset
        @rtype: django.db.models.query.QuerySet
        """
        try:
            queryset = self.queryset

            query = {}
            for key, val in self.request.query_params.dict().items():
                query[key] = val.split(',')
                # TODO strip empty space?

            for key in list(query.keys()):
                val = query[key]
                if type(val) is list:
                    queryset = queryset.filter(**{key+'__in': val})
                    del query[key]

            return queryset.filter(**query)
        except FieldError:
            raise exceptions.APIException
            # TODO more specific exception handling
            # http://www.django-rest-framework.org/api-guide/exceptions/#custom-exception-handling
        except:
            raise exceptions.APIException


class UserViewSet(GenericQueryModelViewSet):
    queryset = models.User.objects.all()
    serializer_class = UserSerializer


class LegislatorViewSet(GenericQueryModelViewSet):
    queryset = models.Legislator.objects.all()
    serializer_class = LegislatorSerializer


class MessageViewSet(viewsets.ModelViewSet):
    queryset = models.Message.objects.all()
    serializer_class = MessageSerializer

    @staticmethod
    def process_inbound_message(django_user, umi, msg, test=False):
        try:
            msg.update_status()

            leg_buckets = models.Legislator.get_leg_buckets_from_emails(umi.members_of_congress, msg.to_originally)
            msg.set_legislators(leg_buckets['contactable'])

            if msg.has_legislators and msg.is_free_to_send():
                msg.queue_to_send()
                emailer.NoReply(django_user).message_queued(msg).send(test=test)
            elif not msg.is_free_to_send():
                emailer.NoReply(django_user).over_rate_limit(msg).send(test=test)
            elif leg_buckets['does_not_represent'] or leg_buckets['non_existent']:
                emailer.NoReply(django_user).message_undeliverable(leg_buckets, msg).send(test=test)

            return True
        except:
            return traceback.format_exc()

    @list_route(methods=['post'])
    def send(self, request):
        try:
            params = request.data
            django_user = request.user
            umi = django_user.user.default_info

            if 'send_date' not in params:
                send_date = datetime.now()
            else:
                try:
                    send_date = datetime.strptime(params['send_date'], '%Y-%m-%dT%H:%M:%S%z')
                except:
                    raise exceptions.APIException('Bad format for send_date. Expected ISO 8601 or %Y-%m-%dT%H:%M:%S%z.')

            new_msg = models.Message.objects.create(
                created_at=send_date,
                to_originally=params['to'],
                subject=params['subject'],
                msgbody=params['body'],
                email_uid=params.get('email_uid',''),
                user_message_info=umi
            )

            sent = self.process_inbound_message(django_user, umi, new_msg, False)
            return Response({'data': self.serializer_class(new_msg).data, 'status': sent})
        except:
            raise exceptions.APIException('Error while trying to submit email.')
