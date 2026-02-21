from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.throttling import BaseThrottle

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


def get_cache_key(request: Request) -> str | None:
    api_key = getattr(request, "auth", None)
    if api_key is None:
        return None
    return f"throttle:api_key:{api_key.key}"


class APIKeyRateThrottle(BaseThrottle):
    """
    Rate-limit to 100 requests per hour per API key using the Redis cache.

    The counter is stored in Redis with a TTL of 3600 seconds. Each request
    increments the counter; once it exceeds the limit, the request is rejected
    with HTTP 429.
    """

    RATE_LIMIT = 100  # requests
    PERIOD_IN_SECONDS = 3600  # 1 hour

    def allow_request(self, request: Request, view: APIView) -> bool:
        key = get_cache_key(request)
        if key is None:
            return True  # unauthenticated, so let auth layer handle it

        current = cache.get(key, 0)
        if current >= self.RATE_LIMIT:
            wait = cache.ttl(key)
            raise Throttled(wait=wait if wait else self.PERIOD_IN_SECONDS)
        print("In allow_request: ", current)

        if current == 0:
            # set TTL on the first request.
            cache.set(key, 1, timeout=self.PERIOD_IN_SECONDS)
        else:
            cache.incr(key)

        return True
