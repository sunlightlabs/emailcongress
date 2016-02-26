from emailcongress import models
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = models.User
        fields = ('email', 'token')


class LegislatorSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = models.Legislator
        fields = ('bioguide_id', 'chamber', 'state', 'district',
                  'title', 'first_name', 'last_name',
                  'contact_form', 'contactable', 'email')


class MessageSerializer(serializers.HyperlinkedModelSerializer):

    to = serializers.CharField(source='to_originally')
    body = serializers.CharField(source='msgbody')

    class Meta:
        model = models.Message
        fields = ('to', 'subject', 'body', 'email_uid')
