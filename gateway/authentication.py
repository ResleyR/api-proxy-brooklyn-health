from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from .models import APIKey


class APIKeyUser:
    """Lightweight user-like object attached to DRF request.user."""

    def __init__(self, api_key: APIKey):
        self.api_key = api_key
        self.pk = api_key.pk
        self.is_authenticated = True

    def __str__(self):
        return self.api_key.name


class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticate requests via the ``X-API-KEY`` header.

    On success the ``request.user`` is set to an ``APIKeyUser`` instance
    and ``request.auth`` is the ``APIKey`` model instance.
    """

    HEADER = "HTTP_X_API_KEY"

    def authenticate_header(self, request: Request) -> str:
        """Return a string for the WWW-Authenticate header."""
        return "API-Key"

    def authenticate(self, request: Request) -> tuple[APIKeyUser, APIKey]:
        key = request.META.get(self.HEADER)

        if not key:
            raise AuthenticationFailed(
                detail="Missing API key. Include it in the X-API-KEY header.",
                code="missing_api_key",
            )

        try:
            api_key = APIKey.objects.get(key=key, is_active=True)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed(
                detail="Invalid or inactive API key.",
                code="invalid_api_key",
            ) from None

        return APIKeyUser(api_key), api_key
