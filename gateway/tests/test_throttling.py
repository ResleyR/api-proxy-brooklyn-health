from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.exceptions import Throttled

from gateway.models import APIKey
from gateway.throttling import APIKeyRateThrottle, get_cache_key


class TestGetCacheKey(TestCase):
    """Tests for the rate limiting cache key generation function."""

    def test_cache_key_format(self):
        """Cache key should include the API key string."""
        api_key = APIKey.objects.create(name="Cache Key Client")
        request = MagicMock()
        request.auth = api_key
        key = get_cache_key(request)
        self.assertEqual(key, f"throttle:api_key:{api_key.key}")

    def test_no_auth_returns_none_key(self):
        """Unauthenticated requests should get not get a cache key."""
        request = MagicMock()
        request.auth = None
        key = get_cache_key(request)
        self.assertIsNone(key)


@patch("gateway.throttling.get_cache_key", return_value="throttle:api_key:key")
@patch("gateway.throttling.cache")
class TestAPIKeyRateThrottle(TestCase):
    """Tests for the Redis-backed rate limiter."""

    def setUp(self):
        self.throttle = APIKeyRateThrottle()
        self.api_key = APIKey.objects.create(name="Throttle Client")

    def _make_request(self):
        """Create a mock request with auth set to our API key."""
        request = MagicMock()
        request.auth = self.api_key
        return request

    def test_rate_limit_constant(self, mock_cache, mock_get_cache_key):
        """The rate limit should be set to 100 requests per hour."""
        self.assertEqual(self.throttle.RATE_LIMIT, 100)
        self.assertEqual(self.throttle.PERIOD_IN_SECONDS, 3600)

    def test_allows_first_request(self, mock_cache, mock_get_cache_key):
        """The first request (counter=0) should be allowed."""
        mock_cache.get.return_value = 0

        request = self._make_request()
        result = self.throttle.allow_request(request, MagicMock())

        self.assertTrue(result)
        mock_cache.incr.assert_not_called()
        mock_cache.set.assert_called_once_with(
            mock_get_cache_key.return_value, 0, timeout=3600
        )

    def test_allows_request_under_limit(self, mock_cache, mock_get_cache_key):
        """Requests under the rate limit should pass."""
        mock_cache.get.return_value = 50  # well under 100

        request = self._make_request()
        result = self.throttle.allow_request(request, MagicMock())

        self.assertTrue(result)
        mock_cache.incr.assert_called_once_with(mock_get_cache_key.return_value)
        # no ttl should be set since counter > 0
        mock_cache.set.assert_not_called()

    def test_blocks_when_limit_exceeded(self, mock_cache, mock_get_cache_key):
        """Should raise Throttled when the counter >= RATE_LIMIT."""
        mock_cache.get.return_value = 100
        mock_cache.ttl.return_value = 1800

        request = self._make_request()
        with self.assertRaises(Throttled) as ctx:
            self.throttle.allow_request(request, MagicMock())

        self.assertEqual(ctx.exception.wait, 1800)

    def test_blocks_when_over_limit(self, mock_cache, mock_get_cache_key):
        """Should also block when the counter is well over the limit."""
        mock_cache.get.return_value = 150
        mock_cache.ttl.return_value = 900

        request = self._make_request()
        with self.assertRaises(Throttled) as ctx:
            self.throttle.allow_request(request, MagicMock())

        self.assertEqual(ctx.exception.wait, 900)

    def test_uses_period_as_fallback_wait(self, mock_cache, mock_get_cache_key):
        """If ttl returns 0/None, fall back to PERIOD."""
        mock_cache.get.return_value = 100
        mock_cache.ttl.return_value = 0

        request = self._make_request()
        with self.assertRaises(Throttled) as ctx:
            self.throttle.allow_request(request, MagicMock())

        self.assertEqual(ctx.exception.wait, self.throttle.PERIOD_IN_SECONDS)

    def test_unauthenticated_request_passes_through(
        self, mock_cache, mock_get_cache_key
    ):
        """Requests with no auth should not be rate-limited."""
        request = MagicMock()
        request.auth = None
        mock_get_cache_key.return_value = None
        result = self.throttle.allow_request(request, MagicMock())
        self.assertTrue(result)
