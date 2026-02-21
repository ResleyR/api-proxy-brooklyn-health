from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from gateway.authentication import APIKeyAuthentication, APIKeyUser
from gateway.models import APIKey


class TestAPIKeyAuthentication(TestCase):
    """Tests for the custom X-API-KEY authentication class."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.auth = APIKeyAuthentication()
        self.api_key = APIKey.objects.create(name="Auth Test Client")

    def test_valid_key_authenticates(self):
        """A valid, active API key should authenticate successfully."""
        request = self.factory.get("/", HTTP_X_API_KEY=self.api_key.key)
        user, auth = self.auth.authenticate(request)
        self.assertIsInstance(user, APIKeyUser)
        self.assertEqual(auth.pk, self.api_key.pk)
        self.assertTrue(user.is_authenticated)

    def test_missing_key_returns_401(self):
        """A request without X-API-KEY should raise AuthenticationFailed."""
        request = self.factory.get("/")
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(ctx.exception.detail.code, "missing_api_key")

    def test_invalid_key_returns_401(self):
        """A request with a wrong key should raise AuthenticationFailed."""
        request = self.factory.get("/", HTTP_X_API_KEY="nonexistent-key")
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(ctx.exception.detail.code, "invalid_api_key")

    def test_inactive_key_returns_401(self):
        """An inactive API key should not authenticate."""
        self.api_key.is_active = False
        self.api_key.save()

        request = self.factory.get("/", HTTP_X_API_KEY=self.api_key.key)
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(ctx.exception.detail.code, "invalid_api_key")


class TestAPIKeyUser(TestCase):
    def test_api_key_user_str(self):
        """APIKeyUser.__str__ should return the key's name."""
        api_key = APIKey.objects.create(name="API Key User Test Client")
        user = APIKeyUser(api_key)
        self.assertEqual(str(user), api_key.name)
