from django.db import IntegrityError
from django.test import TestCase

from gateway.models import APIKey, RequestLog, Service


class TestAPIKey(TestCase):
    """Tests for the APIKey model."""

    def test_auto_generates_key_on_create(self):
        """An API key string is auto-generated when the object is saved."""
        api_key = APIKey.objects.create(name="Test Client")
        self.assertEqual(len(api_key.key), 32)  # uuid4().hex is 32 chars

    def test_key_is_unique(self):
        """Two API keys should have different key values."""
        k1 = APIKey.objects.create(name="Client A")
        k2 = APIKey.objects.create(name="Client B")
        self.assertNotEqual(k1.key, k2.key)

    def test_is_active_defaults_to_true(self):
        api_key = APIKey.objects.create(name="Active Client")
        self.assertTrue(api_key.is_active)

    def test_str_representation(self):
        api_key = APIKey.objects.create(name="My Client")
        expected_prefix = api_key.key[:8]
        self.assertEqual(f"My Client ({expected_prefix}...)", str(api_key))

    def test_key_not_overwritten_on_update(self):
        """Editing an existing APIKey should not regenerate the key."""
        api_key = APIKey.objects.create(name="Original")
        original_key = api_key.key
        api_key.name = "Updated"
        api_key.save()
        api_key.refresh_from_db()
        self.assertEqual(api_key.key, original_key)


class TestService(TestCase):
    """Tests for the Service model."""

    def test_create_service(self):
        service = Service.objects.create(
            name="HTTPBin",
            slug="httpbin",
            base_url="https://httpbin.org",
        )
        self.assertEqual(service.slug, "httpbin")
        self.assertTrue(service.is_active)

    def test_str_representation(self):
        service = Service.objects.create(
            name="HTTPBin",
            slug="httpbin",
            base_url="https://httpbin.org",
        )
        self.assertEqual("HTTPBin -> https://httpbin.org", str(service))

    def test_slug_uniqueness(self):
        Service.objects.create(
            name="First", slug="api", base_url="https://example.com"
        )
        with self.assertRaises(IntegrityError):
            Service.objects.create(
                name="Second", slug="api", base_url="https://other.com"
            )


class TestRequestLog(TestCase):
    """Tests for the RequestLog model."""

    def test_create_log_entry(self):
        api_key = APIKey.objects.create(name="Logger Client")
        service = Service.objects.create(
            name="HTTPBin", slug="httpbin", base_url="https://httpbin.org"
        )
        log = RequestLog.objects.create(
            api_key=api_key,
            service=service,
            method="GET",
            path="/get",
            status_code=200,
            duration_ms=42.5,
        )
        self.assertEqual(log.method, "GET")
        self.assertEqual(log.status_code, 200)
        self.assertIsNotNone(log.timestamp)

    def test_log_allows_null_fks(self):
        """Logs should work even if the API key or service was deleted."""
        log = RequestLog.objects.create(
            api_key=None,
            service=None,
            method="GET",
            path="/test",
            status_code=200,
            duration_ms=10.0,
        )
        self.assertIsNone(log.api_key)
        self.assertIsNone(log.service)

    def test_str_representation(self):
        log = RequestLog.objects.create(
            method="POST",
            path="/submit",
            status_code=201,
            duration_ms=150.0,
        )
        self.assertEqual("[POST] /submit -> 201 (150ms)", str(log))
