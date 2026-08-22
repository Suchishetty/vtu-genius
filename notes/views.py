from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpResponseForbidden
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView
import os

from accounts.models import StudentProfile

from .forms import UploadNotesForm
from .models import Notes


class UploadNotesView(LoginRequiredMixin, CreateView):
    model = Notes
    form_class = UploadNotesForm
    template_name = "notes/upload_notes.html"
    success_url = reverse_lazy("notes:my_notes")
    login_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        try:
            student_profile = StudentProfile.objects.get(user=self.request.user)
        except StudentProfile.DoesNotExist:
            messages.error(
                self.request,
                "Student profile not found. Please complete your profile first.",
            )
            return redirect("dashboard:dashboard")

        form.instance.student = student_profile
        response = super().form_valid(form)
        messages.success(self.request, "Notes uploaded successfully.")
        return response


class MyNotesView(LoginRequiredMixin, ListView):
    model = Notes
    template_name = "notes/my_notes.html"
    ordering = ["-uploaded_at"]
    login_url = reverse_lazy("accounts:login")

    def get_queryset(self):
        try:
            student_profile = self.request.user.studentprofile
        except StudentProfile.DoesNotExist:
            messages.error(
                self.request,
                "Student profile not found. Unable to load your notes.",
            )
            return Notes.objects.none()

        queryset = Notes.objects.filter(student=student_profile).order_by("-uploaded_at")

        search_query = self.request.GET.get("q", "").strip()
        semester = self.request.GET.get("semester", "").strip()

        if search_query:
            queryset = queryset.filter(
                Q(subject__icontains=search_query)
                | Q(unit__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        if semester:
            queryset = queryset.filter(semester=semester)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["selected_semester"] = self.request.GET.get("semester", "").strip()
        context["semester_options"] = [
            ("1", "Semester 1"),
            ("2", "Semester 2"),
            ("3", "Semester 3"),
            ("4", "Semester 4"),
            ("5", "Semester 5"),
            ("6", "Semester 6"),
            ("7", "Semester 7"),
            ("8", "Semester 8"),
        ]
        return context


class DeleteNotesView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get_queryset(self):
        try:
            student_profile = self.request.user.studentprofile
        except StudentProfile.DoesNotExist:
            messages.error(
                self.request,
                "Student profile not found. Unable to delete notes.",
            )
            return Notes.objects.none()

        return Notes.objects.filter(student=student_profile)

    def post(self, request, pk, *args, **kwargs):
        note = get_object_or_404(self.get_queryset(), pk=pk)
        note.delete()
        messages.success(self.request, "Notes deleted successfully.")
        return redirect("notes:my_notes")


class DownloadNotesView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get(self, request, pk, *args, **kwargs):
        try:
            student_profile = request.user.studentprofile
        except StudentProfile.DoesNotExist:
            messages.error(
                request,
                "Student profile not found. Unable to download notes.",
            )
            return HttpResponseForbidden("You are not allowed to download this file.")

        note = Notes.objects.filter(pk=pk).select_related("student").first()
        if note is None or note.student != student_profile:
            return HttpResponseForbidden("You are not allowed to download this file.")

        filename = os.path.basename(note.pdf.name)
        return FileResponse(
            note.pdf.open("rb"),
            as_attachment=True,
            filename=filename,
        )
