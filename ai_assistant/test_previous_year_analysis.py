from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import StudentProfile

from .forms import PreviousYearPaperUploadForm
from .models import PreviousYearPaper
from .previous_year_service import PreviousYearAnalysisService


class PreviousYearAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="paper-a", password="pass")
        self.profile = StudentProfile.objects.create(
            user=self.user,
            full_name="Paper Student A",
            email="paper-a@example.com",
            branch="CSE",
            semester="5",
        )
        self.other_user = User.objects.create_user(username="paper-b", password="pass")
        self.other_profile = StudentProfile.objects.create(
            user=self.other_user,
            full_name="Paper Student B",
            email="paper-b@example.com",
            branch="CSE",
            semester="5",
        )

    @staticmethod
    def pdf_file(name="paper.pdf"):
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4 fake pdf bytes",
            content_type="application/pdf",
        )

    def test_analysis_page_requires_login(self):
        response = self.client.get(reverse("ai_assistant:previous_year_analysis"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_upload_form_rejects_non_pdf_and_oversized_files(self):
        invalid = SimpleUploadedFile("paper.txt", b"not pdf", content_type="text/plain")
        form = PreviousYearPaperUploadForm({
            "subject": "IoT",
            "semester": "5",
            "year": "2025",
            "exam_type": "regular",
        }, {"pdf": invalid})
        self.assertFalse(form.is_valid())
        self.assertIn("Only PDF files are allowed.", form.errors["pdf"][0])

    def test_question_extraction_preserves_main_and_subquestion_wording(self):
        questions = PreviousYearAnalysisService.extract_questions(
            "2025\n1. Explain the IoT communication model. [10]\n"
            "a) Define IoT. [2]\n2) Describe IoT architecture. (5 marks)"
        )
        self.assertEqual(len(questions), 3)
        self.assertEqual(questions[0]["text"], "Explain the IoT communication model. [10]")
        self.assertEqual(questions[0]["marks"], "10")
        self.assertEqual(questions[1]["number"], "1(a)")
        self.assertEqual(questions[1]["marks"], "2")
        self.assertEqual(questions[2]["marks"], "5")

    def test_uploaded_paper_is_owned_by_logged_in_student(self):
        self.client.force_login(self.user)
        extracted = "1. Explain the IoT communication model. [10]"
        with patch(
            "ai_assistant.views.AIService.extract_pdf_text",
            return_value=extracted,
        ):
            response = self.client.post(
                reverse("ai_assistant:previous_year_analysis"),
                {
                    "action": "upload",
                    "subject": "IoT",
                    "semester": "5",
                    "year": "2025",
                    "exam_type": "regular",
                    "pdf": self.pdf_file(),
                },
            )
        self.assertEqual(response.status_code, 302)
        paper = PreviousYearPaper.objects.get()
        self.assertEqual(paper.student, self.profile)
        self.assertEqual(
            paper.extracted_questions[0]["text"],
            "Explain the IoT communication model. [10]",
        )

    def test_analysis_is_filtered_to_current_student_and_counts_repeats(self):
        question = {
            "number": "1",
            "text": "Explain the IoT communication model.",
            "marks": "10",
        }
        for year in (2023, 2025):
            PreviousYearPaper.objects.create(
                student=self.profile,
                subject="IoT",
                semester="5",
                year=year,
                pdf=self.pdf_file(f"{year}.pdf"),
                extracted_text=question["text"],
                extracted_questions=[question],
            )
        PreviousYearPaper.objects.create(
            student=self.other_profile,
            subject="IoT",
            semester="5",
            year=2024,
            pdf=self.pdf_file("other.pdf"),
            extracted_text="1. Explain the IoT communication model.",
            extracted_questions=[question],
        )
        self.client.force_login(self.user)
        with patch("ai_assistant.views.RAGService.search_relevant_chunks", return_value=[]):
            with patch("ai_assistant.previous_year_service.AIService", side_effect=RuntimeError):
                response = self.client.post(
                    reverse("ai_assistant:previous_year_analysis"),
                    {
                        "action": "analyze",
                        "subject": "IoT",
                        "paper_count": "all",
                    },
                )
        self.assertEqual(response.status_code, 200)
        analysis = response.context["analysis"]
        self.assertEqual(analysis["papers_analyzed"], 2)
        self.assertEqual(analysis["repeated_questions"][0]["paper_count"], 2)
        self.assertEqual(analysis["marks_trends"]["10"], 2)
