from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

from dashboard.views import ProfileView


def health_check(request):
    return HttpResponse("ok", content_type="text/plain")

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("notes/", include("notes.urls")),
    path("ai-assistant/", include("ai_assistant.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
