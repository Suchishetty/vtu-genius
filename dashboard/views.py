from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from accounts.models import StudentProfile
from notes.models import Notes


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"
    login_url = reverse_lazy("accounts:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = get_object_or_404(StudentProfile, user=self.request.user)
        student_notes = Notes.objects.filter(student=profile)
        latest_note = student_notes.order_by("-uploaded_at").first()

        context["profile"] = profile
        context["statistics"] = {
            "total_notes": student_notes.count(),
            "total_subjects": student_notes.values("subject").distinct().count(),
            "current_semester": profile.get_semester_display(),
            "latest_upload_date": (
                latest_note.uploaded_at if latest_note else "No uploads yet"
            ),
        }
        return context


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/profile.html"
    login_url = reverse_lazy("accounts:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = get_object_or_404(StudentProfile, user=self.request.user)
        return context
