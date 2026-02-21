from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from gateway.views import ProxyView

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(
        r"^proxy/(?P<service_slug>[\w-]+)/(?P<path>.*)$",
        ProxyView.as_view(),
        name="proxy",
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATIC_ROOT
    )
