from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    # The staff dashboard is the primary back office. Django's own admin is
    # kept mounted as a fallback; drop the line below to remove it entirely.
    path("dashboard/", include("dashboard.urls")),
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
]

if settings.DEBUG:
    # Uploaded service images, logos and team photos.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    # Same files, served by Django because a container host has no web server
    # in front of the app. `static()` above deliberately does nothing when
    # DEBUG is False, so the route has to be spelled out.
    #
    # This only ever reaches MEDIA_ROOT. Resumes live in PRIVATE_MEDIA_ROOT, a
    # separate directory with no URL of its own, downloadable only through
    # dashboard.careers_views.application_resume behind view_application.
    urlpatterns += [
        re_path(
            r"^%s(?P<path>.*)$" % settings.MEDIA_URL.lstrip("/"),
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
