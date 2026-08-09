from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # The staff dashboard is the primary back office. Django's own admin is
    # kept mounted as a fallback; drop the line below to remove it entirely.
    path("dashboard/", include("dashboard.urls")),
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
]

if settings.DEBUG:
    # Uploaded service images. In production the web server serves MEDIA_ROOT.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
