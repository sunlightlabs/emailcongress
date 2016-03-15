from rest_framework import HTTP_HEADER_ENCODING, exceptions
from rest_framework.authentication import TokenAuthentication as rest_framework_TokenAuthentication
from django.utils.translation import ugettext_lazy as _
from emailcongress.models import Token


class TokenAuthentication(rest_framework_TokenAuthentication):
    """
    Simple token based authentication.

    A custom token model may be used, but must have the following properties.

    * key -- The string identifying the token
    * user -- The user to which the token belongs

    http://stackoverflow.com/questions/27043349/how-to-use-custom-token-model-in-django-rest-framework
    """

    model = Token

    def authenticate_credentials(self, key):

        try:
            token = self.model.objects.select_related('user').get(key=key)
        except self.model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_('User inactive or deleted.'))

        if not (token.user.is_superuser or token.user.has_perm('emailcongress.api')):
            raise exceptions.AuthenticationFailed(_("This token doesn't have API permissions. "
                                                    "Request access at https://emailcongress/developers"))

        return (token.user, token)
