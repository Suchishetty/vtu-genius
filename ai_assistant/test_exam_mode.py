from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import StudentProfile
from notes.models import Notes

from .exam_mode_service import ExamModePlanner
from .forms import ExamModeForm
from .models import PreviousYearPaper


class ExamModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exam-a", password="pass")
        self.profile = StudentProfile.objects.create(
            user=self.user,
            full_name="Exam Student A",
            email="exam-a@example.com",
            branch="CSE",
            semester="5",
        )
        self.other_user = User.objects.create_user(username="exam-b", password="pass")
        self.other_profile = StudentProfile.objects.create(
            user=self.other_user,
            full_name="Exam Student B",
            email="exam-b@example.com",
            branch="CSE",
            semester="5",
        )
        Notes.objects.create(
            student=self.profile,
            subject="IoT",
            semester="5",
            unit="Unit 1",
            pdf=ContentFile(b"placeholder", name="iot.pdf"),
        )
        Notes.objects.create(
            student=self.other_profile,
            subject="Private Subject",
            semester="5",
            unit="Unit 1",
            pdf=ContentFile(b"placeholder", name="private.pdf"),
        )

    def valid_form_data(self, **overrides):
        data = {
            "subject": "IoT",
            "exam_date": str(date.today()),
            "study_hours": "2",
            "confidence": "medium",
        }
        data.update(overrides)
        return data

    def test_exam_mode_requires_login(self):
        response = self.client.get(reverse("ai_assistant:exam_mode"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_form_scopes_subject_and_rejects_past_date(self):
        form = ExamModeForm(
            self.valid_form_data(
                subject="Private Subject",
                exam_date=str(date.today() - timedelta(days=1)),
            ),
            student_profile=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Select a subject from your uploaded notes.", form.non_field_errors())

    def test_custom_duration_is_validated_and_resolved(self):
        form = ExamModeForm(
            self.valid_form_data(study_hours="custom", custom_hours="3.5"),
            student_profile=self.profile,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["resolved_hours"], 3.5)

    def test_planner_stays_within_duration_and_keeps_breaks_outside_budget(self):
        chunks = [
            {"text": "Communication model and architecture are explained in detail.", "metadata": {"unit": "Unit 1"}},
            {"text": "Sensors and protocols are explained with examples.", "metadata": {"unit": "Unit 2"}},
            {"text": "Security fundamentals and challenges.", "metadata": {"unit": "Unit 3"}},
        ]
        plan = ExamModePlanner().build_plan("IoT", 8, "low", chunks)
        self.assertLessEqual(plan["study_minutes"], 8 * 60)
        self.assertEqual(sum(item["minutes"] for item in plan["topics"]) + 30, plan["study_minutes"])
        self.assertTrue(any(item["kind"] == "break" for item in plan["schedule"]))

    def test_previous_year_questions_are_used_without_other_student_data(self):
        PreviousYearPaper.objects.create(
            student=self.profile,
            subject="IoT",
            semester="5",
            year=2025,
            pdf=ContentFile(b"placeholder", name="paper-a.pdf"),
            extracted_questions=[{
                "number": "1",
                "text": "Explain the IoT communication model.",
                "marks": "10",
            }],
        )
        PreviousYearPaper.objects.create(
            student=self.other_profile,
            subject="IoT",
            semester="5",
            year=2025,
            pdf=ContentFile(b"placeholder", name="paper-b.pdf"),
            extracted_questions=[{
                "number": "1",
                "text": "Private student question.",
                "marks": "10",
            }],
        )
        self.client.force_login(self.user)
        chunks = [{"text": "Communication model is important.", "metadata": {"unit": "Unit 1"}}]
        with patch("ai_assistant.views.RAGService.search_relevant_chunks", return_value=chunks):
            with patch("ai_assistant.previous_year_service.AIService", side_effect=RuntimeError):
                response = self.client.post(
                    reverse("ai_assistant:exam_mode"),
                    self.valid_form_data(study_hours="4"),
                )
        self.assertEqual(response.status_code, 200)
        plan = response.context["plan"]
        self.assertIn("Explain the IoT communication model.", plan["questions"])
        self.assertNotIn("Private student question.", plan["questions"])
        self.assertTrue(plan["previous_year_available"])

    def test_ollama_or_previous_year_failure_does_not_prevent_notes_plan(self):
        self.client.force_login(self.user)
        chunks = [{"text": "IoT communication model.", "metadata": {"unit": "Unit 1"}}]
        with patch("ai_assistant.views.RAGService.search_relevant_chunks", return_value=chunks):
            response = self.client.post(
                reverse("ai_assistant:exam_mode"),
                self.valid_form_data(study_hours="2"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("plan", response.context)
        self.assertFalse(response.context["plan"]["previous_year_available"])
