from django.urls import path

from . import views


app_name = "notes"


urlpatterns = [
    path(
        "upload/",
        views.UploadNotesView.as_view(),
        name="upload",
    ),
    path(
        "my-notes/",
        views.MyNotesView.as_view(),
        name="my_notes",
    ),
    path(
        "delete/<int:pk>/",
        views.DeleteNotesView.as_view(),
        name="delete",
    ),
    path(
        "download/<int:pk>/",
        views.DownloadNotesView.as_view(),
        name="download",
    ),
]
