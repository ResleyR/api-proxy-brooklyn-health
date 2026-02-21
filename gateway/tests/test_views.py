from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from gateway.models import APIKey, RequestLog, Service

# Disable throttling for proxy integration tests
NO_THROTTLE_DRF = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "gateway.authentication.APIKeyAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [],
}


@override_settings(REST_FRAMEWORK=NO_THROTTLE_DRF)
class TestProxyView(TestCase):
    """Integration tests for the proxy view."""

    @classmethod
    def setUpTestData(cls):
        cls.api_key = APIKey.objects.create(name="Proxy Test Client")
        cls.service = Service.objects.create(
            name="HTTPBin",
            slug="httpbin",
            base_url="https://httpbin.org",
        )

    def setUp(self):
        self.client = APIClient()

    def _auth_headers(self):
        return {"HTTP_X_API_KEY": self.api_key.key}

    def test_missing_api_key_returns_401(self):
        """Requests without X-API-KEY should get 401."""
        response = self.client.get("/proxy/httpbin/get")
        self.assertEqual(response.status_code, 401)

    def test_invalid_api_key_returns_401(self):
        """Requests with a bad API key should get 401."""
        response = self.client.get(
            "/proxy/httpbin/get", HTTP_X_API_KEY="bad-key"
        )
        self.assertEqual(response.status_code, 401)

    def test_unknown_service_returns_404(self):
        """Requesting a nonexistent service slug should get 404."""
        response = self.client.get(
            "/proxy/nonexistent/get", **self._auth_headers()
        )
        self.assertEqual(response.status_code, 404)

    def test_inactive_service_returns_404(self):
        """An inactive service should not be found."""
        Service.objects.create(
            name="Inactive Service",
            slug="inactive-service",
            base_url="https://example.com",
            is_active=False,
        )
        response = self.client.get(
            "/proxy/inactive-service/get", **self._auth_headers()
        )
        self.assertEqual(response.status_code, 404)

    @patch("gateway.views.http_client.request")
    def test_successful_get_proxy(self, mock_request):
        """A valid GET should proxy to upstream and return its response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"origin": "1.2.3.4"}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_request.return_value = mock_response

        response = self.client.get("/proxy/httpbin/get", **self._auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_response.content, response.content)

        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs.kwargs["method"], "GET")
        self.assertIn("httpbin.org/get", call_kwargs.kwargs["url"])

    @patch("gateway.views.http_client.request")
    def test_post_proxy_forwards_body(self, mock_request):
        """A POST should forward the request body upstream."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"created": true}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_request.return_value = mock_response

        response = self.client.post(
            "/proxy/httpbin/post",
            data='{"name": "test"}',
            content_type="application/json",
            **self._auth_headers(),
        )

        self.assertEqual(response.status_code, 201)
        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs.kwargs["method"], "POST")

    @patch("gateway.views.http_client.request")
    def test_query_string_forwarded(self, mock_request):
        """Query parameters should be appended to the upstream URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"{}"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        self.client.get(
            "/proxy/httpbin/get?foo=bar&baz=1", **self._auth_headers()
        )

        call_kwargs = mock_request.call_args
        self.assertIn("foo=bar", call_kwargs.kwargs["url"])
        self.assertIn("baz=1", call_kwargs.kwargs["url"])

    @patch("gateway.views.http_client.request")
    def test_upstream_error_returns_502(self, mock_request):
        """If the upstream request fails, the gateway should return 502."""
        import requests

        mock_request.side_effect = requests.ConnectionError(
            "Connection refused"
        )

        response = self.client.get("/proxy/httpbin/get", **self._auth_headers())

        self.assertEqual(response.status_code, 502)
        self.assertIn(b"Upstream service error", response.content)

    @patch("gateway.views.http_client.request")
    def test_request_is_logged(self, mock_request):
        """Every proxied request should create a RequestLog entry."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        self.assertEqual(RequestLog.objects.count(), 0)

        self.client.get("/proxy/httpbin/get", **self._auth_headers())

        self.assertEqual(RequestLog.objects.count(), 1)
        log = RequestLog.objects.first()
        self.assertEqual(log.method, "GET")
        self.assertEqual(log.path, "/get")
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.api_key, self.api_key)
        self.assertEqual(log.service, self.service)
        self.assertIsNotNone(log.duration_ms)

    @patch("gateway.views.http_client.request")
    def test_failed_request_is_also_logged(self, mock_request):
        """Even 502 upstream errors should be logged."""
        import requests

        mock_request.side_effect = requests.ConnectionError("fail")

        self.client.get("/proxy/httpbin/status/500", **self._auth_headers())

        self.assertEqual(RequestLog.objects.count(), 1)
        log = RequestLog.objects.first()
        self.assertEqual(log.status_code, 502)

    @patch("gateway.views.http_client.request")
    def test_api_key_header_not_forwarded(self, mock_request):
        """The X-API-KEY header should be stripped before forwarding."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        self.client.get("/proxy/httpbin/get", **self._auth_headers())

        call_kwargs = mock_request.call_args
        forwarded_headers = call_kwargs.kwargs["headers"]
        self.assertNotIn("x-api-key", forwarded_headers)

    @patch("gateway.views.http_client.request")
    def test_custom_headers_forwarded(self, mock_request):
        """Custom X- headers from the client should be forwarded upstream."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        self.client.get(
            "/proxy/httpbin/get",
            HTTP_X_CUSTOM_HEADER="custom-value",
            **self._auth_headers(),
        )

        call_kwargs = mock_request.call_args
        forwarded_headers = call_kwargs.kwargs["headers"]
        self.assertEqual(
            forwarded_headers.get("x-custom-header"), "custom-value"
        )

    @patch("gateway.views.http_client.request")
    def test_put_method(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.client.put(
            "/proxy/httpbin/put",
            data='{"update": true}',
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_args.kwargs["method"], "PUT")

    @patch("gateway.views.http_client.request")
    def test_delete_method(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.client.delete(
            "/proxy/httpbin/delete", **self._auth_headers()
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(mock_request.call_args.kwargs["method"], "DELETE")

    @patch("gateway.views.http_client.request")
    def test_patch_method(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        response = self.client.patch(
            "/proxy/httpbin/patch",
            data='{"partial": true}',
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_args.kwargs["method"], "PATCH")

    @patch("gateway.views.http_client.request")
    def test_safe_response_headers_forwarded(self, mock_request):
        """Safe upstream response headers should be passed through."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {
            "Content-Type": "application/json",
            "X-Request-Id": "abc-123",
            "Cache-Control": "no-cache",
        }
        mock_request.return_value = mock_response

        response = self.client.get("/proxy/httpbin/get", **self._auth_headers())

        self.assertEqual(response["X-Request-Id"], "abc-123")
        self.assertEqual(response["Cache-Control"], "no-cache")

    @patch("gateway.views.http_client.request")
    def test_unsafe_response_headers_stripped(self, mock_request):
        """Not all headers should be forwarded to the client."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {
            "Content-Type": "text/plain",
            "Content-Encoding": "gzip",
            "Content-Length": "999",
            "Transfer-Encoding": "chunked",
            "Connection": "keep-alive",
        }
        mock_request.return_value = mock_response

        response = self.client.get("/proxy/httpbin/get", **self._auth_headers())

        self.assertNotIn("Content-Encoding", response.headers)
        # Django sets the actual content length
        self.assertEqual(response.headers["Content-Length"], "2")
        self.assertNotIn("Transfer-Encoding", response.headers)
        self.assertNotIn("Connection", response.headers)

    @patch("gateway.views.http_client.request")
    def test_default_content_type_fallback(self, mock_request):
        """Without Content-Type, response should use octet-stream."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\x00\x01\x02"
        mock_response.headers = {}  # no Content-Type
        mock_request.return_value = mock_response

        response = self.client.get(
            "/proxy/httpbin/bytes", **self._auth_headers()
        )

        self.assertEqual(response["Content-Type"], "application/octet-stream")

    @patch("gateway.views.http_client.request")
    def test_content_type_forwarded_from_request(self, mock_request):
        """Content-Type from the request body should be forwarded."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        self.client.post(
            "/proxy/httpbin/post",
            data='{"key": "value"}',
            content_type="application/json",
            **self._auth_headers(),
        )

        forwarded = mock_request.call_args.kwargs["headers"]
        self.assertEqual(forwarded.get("content-type"), "application/json")

    @patch("gateway.views.http_client.request")
    def test_host_and_cookie_headers_excluded(self, mock_request):
        """Host and Cookie headers should be stripped."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"OK"
        mock_response.headers = {}
        mock_request.return_value = mock_response

        self.client.get(
            "/proxy/httpbin/get",
            HTTP_HOST="evil.com",
            HTTP_COOKIE="session=abc",
            **self._auth_headers(),
        )

        forwarded = mock_request.call_args.kwargs["headers"]
        self.assertNotIn("host", forwarded)
        self.assertNotIn("cookie", forwarded)
