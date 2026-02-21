import time

import requests as http_client
from django.http import HttpResponse
from rest_framework.views import APIView

from .models import RequestLog, Service


class ProxyView(APIView):
    """
    Catch-all view that proxies requests to a registered upstream service.

    URL pattern: /proxy/<service_slug>/<path>

    - Resolves the service by slug.
    - Forwards method, headers, query params, and body.
    - Logs the request metadata to the database.
    - Returns the upstream response as-is to the client.
    """

    FORWARDED_HEADER_PREFIXES = (
        "content-type",
        "accept",
        "authorization",
        "x-",
    )
    EXCLUDED_HEADERS = {"host", "x-api-key", "cookie"}

    def get(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def head(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def options(self, request, *args, **kwargs):
        return self._proxy(request, *args, **kwargs)

    def _proxy(self, request, service_slug: str, path: str):
        """Proxy a request to an upstream service."""

        try:
            service = Service.objects.get(slug=service_slug, is_active=True)
        except Service.DoesNotExist:
            # could have done Response from DRF, but need HttpResponse for the
            # proxied response, so better to use the same class instead.
            return HttpResponse(
                '{"detail": "Service not found."}',
                status=404,
                content_type="application/json",
            )

        upstream_url = f"{service.base_url.rstrip('/')}/{path}"
        if request.META.get("QUERY_STRING"):
            upstream_url += f"?{request.META['QUERY_STRING']}"
        headers = self._extract_headers(request)

        start = time.perf_counter()
        try:
            upstream_response = http_client.request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                data=request.body or None,
                timeout=30,
                allow_redirects=False,
            )
            status_code = upstream_response.status_code
            response_body = upstream_response.content
            response_headers = dict(upstream_response.headers)
        except http_client.RequestException as exc:
            status_code = 502
            response_body = (
                f'{{"detail": "Upstream service error: {exc}"}}'.encode()
            )
            response_headers = {}
        duration_ms = (time.perf_counter() - start) * 1000

        api_key = getattr(request, "auth", None)
        RequestLog.objects.create(
            api_key=api_key,
            service=service,
            method=request.method,
            path=f"/{path}",
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
        )

        response = HttpResponse(
            content=response_body,
            status=status_code,
            content_type=response_headers.get(
                "Content-Type", "application/octet-stream"
            ),
        )

        # Forward safe response headers
        for header, value in response_headers.items():
            lower = header.lower()
            if lower not in (
                "content-encoding",
                "content-length",
                "transfer-encoding",
                "connection",
            ):
                response[header] = value

        return response

    def _extract_headers(self, request):
        """Extract request headers to forward upstream."""
        headers = {}
        for meta_key, meta_value in request.META.items():
            if meta_key.startswith("HTTP_"):
                header_name = meta_key[5:].replace("_", "-").lower()
                if header_name in self.EXCLUDED_HEADERS:
                    continue
                headers[header_name] = meta_value
        # Content-Type is not prefixed with HTTP_ in Django
        content_type = request.META.get("CONTENT_TYPE")
        if content_type:
            headers["content-type"] = content_type
        return headers
