import uuid

from django.db import models


class APIKey(models.Model):
    """Client API key for authenticating gateway requests."""

    name = models.CharField(
        max_length=255,
        help_text="A friendly label for this API key (e.g. client name).",
    )
    key = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Auto-generated API key.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key[:8]}...)"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = uuid.uuid4().hex
        super().save(*args, **kwargs)


class Service(models.Model):
    """An upstream/downstream service that the gateway can proxy requests to."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(
        unique=True,
        help_text="URL path prefix used to route to this service (e.g. 'httpbin').",
    )
    base_url = models.URLField(
        help_text="Base URL of the upstream service (e.g. https://httpbin.org).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} -> {self.base_url}"


class RequestLog(models.Model):
    """Audit log for every proxied request."""

    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_logs",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_logs",
    )
    method = models.CharField(max_length=10)
    path = models.TextField()
    status_code = models.PositiveIntegerField()
    duration_ms = models.FloatField(
        help_text="Round-trip time in milliseconds.",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Request Log"
        verbose_name_plural = "Request Logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return (
            f"[{self.method}] {self.path} -> {self.status_code} "
            f"({self.duration_ms:.0f}ms)"
        )
