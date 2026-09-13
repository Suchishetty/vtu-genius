from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import StudentProfile
from notes.models import Notes

from .forms import ExpectedQuestionsForm
from .views import ExpectedQuestionsView


class ExpectedQuestionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student-a", password="pass")
        self.profile = StudentProfile.objects.create(
            user=self.user,
            full_name="Student A",
            email="student-a@example.com",
            branch="CSE",
            semester="5",
        )
        self.other_user = User.objects.create_user(username="student-b", password="pass")
        self.other_profile = StudentProfile.objects.create(
            user=self.other_user,
            full_name="Student B",
            email="student-b@example.com",
            branch="CSE",
            semester="5",
        )
        self.note = Notes.objects.create(
            student=self.profile,
            subject="Internet of Things",
            semester="5",
            unit="Unit 1",
            pdf=ContentFile(b"placeholder", name="student-a.pdf"),
        )
        Notes.objects.create(
            student=self.other_profile,
            subject="Private Subject",
            semester="5",
            unit="Unit 9",
            pdf=ContentFile(b"placeholder", name="student-b.pdf"),
        )

    def test_form_only_offers_current_students_subjects_and_units(self):
        form = ExpectedQuestionsForm(student_profile=self.profile)
        self.assertEqual(
            list(form.fields["subject"].choices),
            [("Internet of Things", "Internet of Things")],
        )
        self.assertIn(("Unit 1", "Unit 1"), form.fields["unit"].choices)
        self.assertNotIn(("Private Subject", "Private Subject"), form.fields["subject"].choices)

    def test_foreign_subject_is_rejected_before_rag(self):
        form = ExpectedQuestionsForm(
            {"subject": "Private Subject", "unit": "Unit 9", "marks": "10", "question_count": "5"},
            student_profile=self.profile,
        )
        self.assertFalse(form.is_valid())

    def test_generation_filters_rag_to_student_subject_and_unit(self):
        self.client.force_login(self.user)
        chunks = [{
            "text": "The IoT communication model is explained in detail.",
            "metadata": {"subject": "Internet of Things", "unit": "Unit 1", "semester": "5"},
            "distance": 0.1,
        }]
        with patch("ai_assistant.views.RAGService.search_relevant_chunks", return_value=chunks) as search:
            with patch("ai_assistant.views.AIService") as ai_service:
                ai_service.return_value.generate_response.return_value = (
                    "1. Explain the IoT communication model.\n"
                    "Priority: HIGH\nMarks: 10\n"
                    "Reason: Explained in detail in the uploaded notes."
                )
                response = self.client.post(
                    reverse("ai_assistant:expected_questions"),
                    {"subject": "Internet of Things", "unit": "Unit 1", "marks": "10", "question_count": "5"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explain the IoT communication model.")
        search.assert_called_once_with(
            self.profile,
            search.call_args.args[1],
            top_k=12,
            subject="Internet of Things",
            unit="Unit 1",
        )

    def test_parser_orders_priorities_and_removes_duplicates(self):
        response = (
            "1. Define the model.\nPriority: LOW\nMarks: 2\nReason: Basic definition.\n"
            "2. Explain the model.\nPriority: HIGH\nMarks: 10\nReason: Detailed topic.\n"
            "3. Explain the model.\nPriority: HIGH\nMarks: 10\nReason: Duplicate."
        )
        questions = ExpectedQuestionsView._parse_expected_questions(response, 5)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["priority"], "HIGH")
        self.assertEqual(questions[1]["priority"], "LOW")
