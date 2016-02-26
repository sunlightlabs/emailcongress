from rest_framework.authentication import TokenAuthentication as rest_framework_TokenAuthentication
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
