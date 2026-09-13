from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView
import logging
import re

from accounts.models import StudentProfile
from notes.models import Notes

from .models import AIConversation, AIMessage
from .forms import (
    ExpectedQuestionsForm,
    ExamModeForm,
    PreviousYearAnalysisForm,
    PreviousYearPaperUploadForm,
    QuestionGeneratorForm,
)
from .rag_service import RAGService
from .services import AIService
from .models import PreviousYearPaper
from .previous_year_service import PreviousYearAnalysisService
from .exam_mode_service import ExamModePlanner


logger = logging.getLogger(__name__)


QUESTION_GENERATOR_INSTRUCTIONS = """
You generate VTU exam-oriented questions using only the retrieved uploaded-note
context. Do not use general knowledge and do not invent topics, concepts,
examples, protocols, technologies, components, facts, or wording not supported
by that context. Match the requested marks exactly in the scope of each
question. If the retrieved note context does not contain enough information,
respond exactly: This information is not specified in the uploaded notes.

Return only the requested questions. Put one question on each line in this
format: 1. Question text
Do not add answers, headings, commentary, marks, or Markdown formatting.
"""


EXPECTED_QUESTIONS_INSTRUCTIONS = """
You identify high-priority expected exam questions using ONLY the supplied
retrieved uploaded-note context. These are predictions, not guaranteed exam
questions. Never use web search, general VTU knowledge, or information absent
from the context. Do not invent unsupported topics, facts, or importance.

Prioritize concepts repeatedly emphasized, major headings, definitions,
fundamentals, detailed explanations, multiple subtopics, processes,
architectures, models, algorithms, comparisons, advantages, and disadvantages
only when they appear in the context. Match the requested marks naturally.
Do not force a question into a marks category if the notes do not support it.
Do not generate answers. Do not repeat questions. Return fewer questions when
the notes do not support the requested count.

Return only one item per block in this exact format:
1. Question text
Priority: HIGH
Marks: 10
Reason: Topic is explained in detail in the uploaded notes.

Use HIGH, MEDIUM, or LOW only when supported by evidence. Keep each reason
short. If no supported question can be made, return exactly:
The uploaded notes did not contain enough supported material.
"""


class AIAssistantView(LoginRequiredMixin, TemplateView):

    template_name = "ai_assistant/assistant.html"

    login_url = reverse_lazy("accounts:login")

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        try:

            student_profile = StudentProfile.objects.get(
                user=self.request.user
            )

        except StudentProfile.DoesNotExist:

            context["conversation"] = None
            context["conversation_messages"] = []

            return context

        conversation = (
            AIConversation.objects
            .filter(student=student_profile)
            .prefetch_related("messages")
            .first()
        )

        context["conversation"] = conversation

        if conversation:

            context["conversation_messages"] = (
                conversation.messages
                .all()
                .order_by("created_at")
            )

        else:

            context["conversation_messages"] = []

        return context


class AskAIView(LoginRequiredMixin, View):

    login_url = reverse_lazy("accounts:login")

    success_url = reverse_lazy(
        "ai_assistant:assistant"
    )

    def post(self, request, *args, **kwargs):

        # =====================================================
        # 1. GET QUESTION
        # =====================================================

        message_text = request.POST.get(
            "message",
            "",
        ).strip()

        if not message_text:

            messages.error(
                request,
                "Message cannot be empty.",
            )

            return redirect(self.success_url)

        # =====================================================
        # 2. GET STUDENT PROFILE
        # =====================================================

        try:

            student_profile = StudentProfile.objects.get(
                user=request.user
            )

        except StudentProfile.DoesNotExist:

            messages.error(
                request,
                "Student profile not found. Please complete your profile first.",
            )

            return redirect("dashboard:dashboard")

        # =====================================================
        # 3. GET OR CREATE CONVERSATION
        # =====================================================

        conversation, _ = AIConversation.objects.get_or_create(
            student=student_profile,
        )

        # =====================================================
        # 4. GET RECENT HISTORY BEFORE SAVING CURRENT MESSAGE
        # =====================================================
        #
        # Important:
        # We collect the previous messages first.
        # This prevents the current question from being duplicated.
        # =====================================================

        conversation_history = list(
            conversation.messages
            .order_by("-created_at")
            .values(
                "role",
                "content",
            )[:6]
        )

        conversation_history.reverse()

        # =====================================================
        # 5. SAVE CURRENT QUESTION
        # =====================================================

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.ROLE_USER,
            content=message_text,
        )

        # =====================================================
        # 6. BUILD RELEVANT NOTES CONTEXT
        # =====================================================

        try:

            notes_context = self._build_notes_context(
                student_profile,
                message_text,
            )

        except Exception as exc:

            print(
                f"Notes context error: "
                f"{type(exc).__name__}: {exc}"
            )

            notes_context = ""

        # =====================================================
        # 7. CREATE AI SERVICE
        # =====================================================

        try:

            ai_service = AIService()

        except ImproperlyConfigured as exc:

            print(
                f"{type(exc).__name__}: {exc}"
            )

            messages.error(
                request,
                str(exc),
            )

            return redirect(self.success_url)

        # =====================================================
        # 8. GENERATE AI RESPONSE
        # =====================================================

        try:

            assistant_response = ai_service.generate_response(
                message_text,
                conversation_history=conversation_history,
                notes_context=notes_context,
            )

        except Exception as exc:

            print(
                f"{type(exc).__name__}: {exc}"
            )

            messages.error(
                request,
                str(exc),
            )

            return redirect(self.success_url)

        # =====================================================
        # 9. SAVE AI RESPONSE
        # =====================================================

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.ROLE_ASSISTANT,
            content=assistant_response,
        )

        # =====================================================
        # 10. RETURN TO ASSISTANT PAGE
        # =====================================================

        return redirect(self.success_url)

    # =========================================================
    # BUILD NOTES CONTEXT
    # =========================================================

    def _build_notes_context(
        self,
        student_profile,
        question,
    ):
        """
        Retrieves the most relevant indexed note chunks and sends only
        those chunks to Ollama. If ChromaDB is unavailable, retain the
        existing PDF-based context path so asking a question still works.

        This prevents the entire notes library from being sent
        for every question.
        """

        try:
            chunks = RAGService().search_relevant_chunks(
                student_profile,
                question,
                top_k=5,
            )
            note_details = [
                {
                    "note_id": chunk["metadata"].get("note_id"),
                    "subject": chunk["metadata"].get("subject", ""),
                }
                for chunk in chunks
            ]
            logger.info(
                "RAG retrieval succeeded for student_id=%s: chunks=%d notes=%s",
                student_profile.pk,
                len(chunks),
                note_details,
            )

            if chunks:
                return "\n\n============================\n\n".join(
                    "\n".join(
                        [
                            "RETRIEVED NOTE CHUNK:",
                            f"NOTE ID: {chunk['metadata'].get('note_id', '')}",
                            f"SUBJECT: {chunk['metadata'].get('subject', '')}",
                            f"SEMESTER: {chunk['metadata'].get('semester', '')}",
                            f"UNIT: {chunk['metadata'].get('unit', '')}",
                            "",
                            chunk["text"],
                        ]
                    )
                    for chunk in chunks
                )
        except Exception:
            # Preserve the existing PDF-based retrieval path if RAG is unavailable.
            logger.exception(
                "RAG retrieval failed for student_id=%s; using PDF-context fallback",
                student_profile.pk,
            )

        logger.info(
            "Using PDF-context fallback for student_id=%s",
            student_profile.pk,
        )

        notes = list(
            Notes.objects
            .filter(student=student_profile)
            .order_by("-uploaded_at")[:10]
        )

        if not notes:

            return ""

        # -----------------------------------------------------
        # Create AI service only once
        # -----------------------------------------------------

        ai_service = AIService()

        # -----------------------------------------------------
        # Calculate relevance
        # -----------------------------------------------------

        scored_notes = []

        for note in notes:

            score = ai_service.calculate_note_relevance(
                note,
                question,
            )

            scored_notes.append(
                (
                    score,
                    note,
                )
            )

        # -----------------------------------------------------
        # Sort by relevance
        # -----------------------------------------------------

        scored_notes.sort(
            key=lambda item: (
                item[0],
                item[1].uploaded_at,
            ),
            reverse=True,
        )

        # -----------------------------------------------------
        # Select relevant notes
        # -----------------------------------------------------
        #
        # If a strong match exists, use up to 2 notes.
        #
        # Otherwise use only the newest note.
        # -----------------------------------------------------

        relevant_notes = [
            note
            for score, note in scored_notes
            if score > 0
        ][:2]

        if not relevant_notes:

            relevant_notes = [
                scored_notes[0][1]
            ]

        logger.info(
            "PDF-context fallback selected for student_id=%s: note_ids=%s subjects=%s",
            student_profile.pk,
            [note.pk for note in relevant_notes],
            [note.subject for note in relevant_notes],
        )

        # -----------------------------------------------------
        # Extract text
        # -----------------------------------------------------

        context_parts = []

        for note in relevant_notes:

            if not note.pdf:

                continue

            try:

                text = ai_service.extract_pdf_text(
                    note.pdf,
                    max_chars=10000,
                )

            except Exception as exc:

                print(
                    f"PDF extraction error: "
                    f"{type(exc).__name__}: {exc}"
                )

                continue

            if not text:

                continue

            context_parts.append(
                "\n".join(
                    [
                        f"SUBJECT: {note.subject}",
                        f"SEMESTER: {note.get_semester_display()}",
                        f"UNIT: {note.unit}",
                        "",
                        text,
                    ]
                )
            )

        return "\n\n============================\n\n".join(
            context_parts
        )


class QuestionGeneratorView(LoginRequiredMixin, View):
    """Generate exam questions from Chroma chunks owned by the current student."""

    template_name = "ai_assistant/question_generator.html"
    login_url = reverse_lazy("accounts:login")

    def get(self, request, *args, **kwargs):
        student_profile = self._get_student_profile(request)
        if student_profile is None:
            return redirect("dashboard:dashboard")
        return render(
            request,
            self.template_name,
            {"form": QuestionGeneratorForm(student_profile=student_profile)},
        )

    def post(self, request, *args, **kwargs):
        student_profile = self._get_student_profile(request)
        if student_profile is None:
            return redirect("dashboard:dashboard")

        form = QuestionGeneratorForm(request.POST, student_profile=student_profile)
        context = {"form": form}
        if not form.is_valid():
            return render(request, self.template_name, context)

        note = form.cleaned_data["note"]
        subject = form.cleaned_data["subject"]
        unit = form.cleaned_data["unit"]
        marks = int(form.cleaned_data["marks"])
        question_count = int(form.cleaned_data["question_count"])
        retrieval_query = (
            f"Important VTU examination questions for {subject}, {unit}. "
            "Definitions, concepts, working, architecture, and applications."
        )

        try:
            chunks = RAGService().search_relevant_chunks(
                student_profile,
                retrieval_query,
                top_k=8,
                note_id=note.pk,
            )
        except Exception:
            logger.exception(
                "Question generator RAG retrieval failed for student_id=%s note_id=%s",
                student_profile.pk,
                note.pk,
            )
            context["generation_error"] = (
                "Unable to retrieve this note right now. Please try again."
            )
            return render(request, self.template_name, context)

        logger.info(
            "Question generator retrieved chunks=%d student_id=%s note_id=%s subject=%s",
            len(chunks),
            student_profile.pk,
            note.pk,
            subject,
        )
        if not chunks:
            context["generation_error"] = (
                "This information is not specified in the uploaded notes."
            )
            return render(request, self.template_name, context)

        notes_context = self._build_retrieved_context(chunks)
        prompt = (
            f"Generate exactly {question_count} important VTU exam questions for "
            f"{subject}, {unit}, worth {marks} marks each."
        )

        try:
            response = AIService().generate_response(
                prompt,
                notes_context=notes_context,
                system_instructions=QUESTION_GENERATOR_INSTRUCTIONS,
            )
        except Exception as exc:
            logger.exception(
                "Question generation failed for student_id=%s note_id=%s",
                student_profile.pk,
                note.pk,
            )
            context["generation_error"] = str(exc)
            return render(request, self.template_name, context)

        questions = self._parse_questions(response, question_count)
        if not questions:
            context["generation_error"] = response.strip()
            return render(request, self.template_name, context)

        context["generated_questions"] = [
            {
                "number": number,
                "text": question,
                "marks": marks,
                "subject": subject,
                "unit": unit,
            }
            for number, question in enumerate(questions, start=1)
        ]
        return render(request, self.template_name, context)

    @staticmethod
    def _get_student_profile(request):
        try:
            return StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            messages.error(
                request,
                "Student profile not found. Please complete your profile first.",
            )
            return None

    @staticmethod
    def _build_retrieved_context(chunks):
        return "\n\n============================\n\n".join(
            "\n".join(
                [
                    "RETRIEVED NOTE CHUNK:",
                    f"SUBJECT: {chunk['metadata'].get('subject', '')}",
                    f"SEMESTER: {chunk['metadata'].get('semester', '')}",
                    f"UNIT: {chunk['metadata'].get('unit', '')}",
                    "",
                    chunk["text"],
                ]
            )
            for chunk in chunks
        )

    @staticmethod
    def _parse_questions(response, question_count):
        questions = []
        current_question = []

        for line in response.splitlines():
            match = re.match(r"^\s*\d+[.)]\s*(.+)$", line)
            if match:
                if current_question:
                    questions.append(" ".join(current_question))
                current_question = [match.group(1).strip()]
            elif current_question and line.strip():
                current_question.append(line.strip())

        if current_question:
            questions.append(" ".join(current_question))

        return questions[:question_count]


class ExpectedQuestionsView(LoginRequiredMixin, View):
    """Predict likely questions from only the current student's filtered RAG context."""

    template_name = "ai_assistant/expected_questions.html"
    login_url = reverse_lazy("accounts:login")
    marks_choices = {"all", "2", "5", "10", "15", "20"}
    count_choices = {"5", "10", "15"}

    def get(self, request, *args, **kwargs):
        student_profile = self._get_student_profile(request)
        if student_profile is None:
            return redirect("dashboard:dashboard")
        form = ExpectedQuestionsForm(student_profile=student_profile)
        return render(request, self.template_name, self._context(form, student_profile))

    def post(self, request, *args, **kwargs):
        student_profile = self._get_student_profile(request)
        if student_profile is None:
            return redirect("dashboard:dashboard")

        form = ExpectedQuestionsForm(request.POST, student_profile=student_profile)
        context = self._context(form, student_profile)
        if not form.is_valid():
            return render(request, self.template_name, context)

        subject = form.cleaned_data["subject"]
        unit = form.cleaned_data["unit"]
        marks = form.cleaned_data["marks"]
        question_count = int(form.cleaned_data["question_count"])
        retrieval_query = self._retrieval_query(subject, unit, marks)

        try:
            chunks = RAGService().search_relevant_chunks(
                student_profile,
                retrieval_query,
                top_k=12,
                subject=subject,
                unit=None if unit == "all" else unit,
            )
        except Exception:
            logger.exception(
                "Expected-question RAG retrieval failed for student_id=%s subject=%s unit=%s",
                student_profile.pk,
                subject,
                unit,
            )
            context["generation_error"] = (
                "Your notes could not be searched right now. Please try again."
            )
            return render(request, self.template_name, context)

        if not chunks:
            context["generation_error"] = (
                "No uploaded note content was found for this subject and unit."
            )
            return render(request, self.template_name, context)

        prompt = self._generation_prompt(subject, unit, marks, question_count)
        notes_context = QuestionGeneratorView._build_retrieved_context(chunks)
        try:
            response = AIService().generate_response(
                prompt,
                notes_context=notes_context,
                system_instructions=EXPECTED_QUESTIONS_INSTRUCTIONS,
            )
        except ImproperlyConfigured:
            context["generation_error"] = (
                "The AI service is unavailable. Please start Ollama and try again."
            )
            return render(request, self.template_name, context)
        except Exception:
            logger.exception(
                "Expected-question generation failed for student_id=%s",
                student_profile.pk,
            )
            context["generation_error"] = (
                "Expected questions could not be generated right now. Please try again."
            )
            return render(request, self.template_name, context)

        questions = self._parse_expected_questions(response, question_count)
        if not questions:
            context["generation_error"] = (
                "The uploaded notes did not contain enough supported material."
            )
            return render(request, self.template_name, context)

        context.update(
            {
                "generated_questions": questions,
                "selected_subject": subject,
                "selected_unit": unit,
                "selected_marks": "All Marks" if marks == "all" else f"{marks} Marks",
                "prediction_notice": True,
            }
        )
        return render(request, self.template_name, context)

    @staticmethod
    def _get_student_profile(request):
        try:
            return StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            messages.error(
                request,
                "Student profile not found. Please complete your profile first.",
            )
            return None

    @staticmethod
    def _context(form, student_profile):
        notes = Notes.objects.filter(student=student_profile)
        subject_units = {}
        for subject in notes.values_list("subject", flat=True).distinct():
            subject_units[subject] = list(
                notes.filter(subject=subject)
                .values_list("unit", flat=True)
                .distinct()
            )
        return {
            "form": form,
            "subject_units": subject_units,
            "has_notes": notes.exists(),
        }

    @staticmethod
    def _retrieval_query(subject, unit, marks):
        marks_text = "all marks" if marks == "all" else f"{marks} mark"
        unit_text = "all units" if unit == "all" else unit
        return (
            f"High-priority expected exam topics for {subject}, {unit_text}, {marks_text}. "
            "Find supported definitions, fundamentals, detailed concepts, processes, "
            "architectures, algorithms, comparisons, and advantages or limitations."
        )

    @staticmethod
    def _generation_prompt(subject, unit, marks, question_count):
        marks_text = "all marks, balanced by the available content" if marks == "all" else f"{marks} marks"
        unit_text = "all units" if unit == "all" else unit
        return (
            f"Generate up to {question_count} high-priority expected questions for "
            f"{subject}, {unit_text}, for {marks_text}. Use only the retrieved notes."
        )

    @staticmethod
    def _parse_expected_questions(response, question_count):
        questions = []
        current = None
        seen = set()
        for raw_line in response.splitlines():
            line = raw_line.strip().strip("*")
            match = re.match(r"^\s*\d+[.)]\s*(.+)$", line)
            if match:
                if current and current.get("text"):
                    ExpectedQuestionsView._append_unique(questions, seen, current)
                current = {
                    "text": match.group(1).strip(),
                    "priority": "MEDIUM",
                    "marks": "",
                    "reason": "Supported by the uploaded notes.",
                }
                continue
            if current is None or not line:
                continue
            key, separator, value = line.partition(":")
            if not separator:
                continue
            key = key.lower().strip()
            value = value.strip().strip("*")
            if key == "priority" and value.upper() in {"HIGH", "MEDIUM", "LOW"}:
                current["priority"] = value.upper()
            elif key == "marks":
                current["marks"] = value
            elif key == "reason":
                current["reason"] = value
        if current and current.get("text"):
            ExpectedQuestionsView._append_unique(questions, seen, current)
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        questions.sort(key=lambda item: order[item["priority"]])
        for number, question in enumerate(questions[:question_count], start=1):
            question["number"] = number
        return questions[:question_count]

    @staticmethod
    def _append_unique(questions, seen, question):
        normalized = re.sub(r"\W+", " ", question["text"].lower()).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            questions.append(question)


class PreviousYearAnalysisView(LoginRequiredMixin, View):
    """Upload and analyze only previous-year papers owned by the current student."""

    template_name = "ai_assistant/previous_year_analysis.html"
    login_url = reverse_lazy("accounts:login")

    def get(self, request, *args, **kwargs):
        profile = self._get_student_profile(request)
        if profile is None:
            return redirect("dashboard:dashboard")
        return render(request, self.template_name, self._base_context(profile))

    def post(self, request, *args, **kwargs):
        profile = self._get_student_profile(request)
        if profile is None:
            return redirect("dashboard:dashboard")

        if request.POST.get("action") == "upload":
            upload_form = PreviousYearPaperUploadForm(request.POST, request.FILES)
            context = self._base_context(profile, upload_form=upload_form)
            if not upload_form.is_valid():
                return render(request, self.template_name, context)
            paper = upload_form.save(commit=False)
            paper.student = profile
            paper.save()
            self._cache_extraction(paper)
            if paper.extraction_error:
                messages.error(request, paper.extraction_error)
            else:
                messages.success(request, "Previous-year question paper uploaded successfully.")
            return redirect("ai_assistant:previous_year_analysis")

        analysis_form = PreviousYearAnalysisForm(
            request.POST,
            student_profile=profile,
        )
        context = self._base_context(profile, analysis_form=analysis_form)
        if not analysis_form.is_valid():
            return render(request, self.template_name, context)

        cleaned = analysis_form.cleaned_data
        papers = PreviousYearPaper.objects.filter(
            student=profile,
            subject=cleaned["subject"],
        )
        if cleaned.get("year_from"):
            papers = papers.filter(year__gte=cleaned["year_from"])
        if cleaned.get("year_to"):
            papers = papers.filter(year__lte=cleaned["year_to"])
        papers = papers.order_by("-year", "-uploaded_at")
        if cleaned["paper_count"] != "all":
            papers = papers[: int(cleaned["paper_count"])]
        papers = list(papers)

        if not papers:
            context["analysis_error"] = "No readable question papers match those filters."
            return render(request, self.template_name, context)

        analysis = PreviousYearAnalysisService.analyze(
            papers,
            unit_mapper=lambda question: self._map_unit(
                profile,
                cleaned["subject"],
                question,
            ),
        )
        context.update(
            {
                "analysis": analysis,
                "selected_subject": cleaned["subject"],
                "selected_year_from": cleaned.get("year_from"),
                "selected_year_to": cleaned.get("year_to"),
            }
        )
        return render(request, self.template_name, context)

    @staticmethod
    def _get_student_profile(request):
        try:
            return StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            messages.error(
                request,
                "Student profile not found. Please complete your profile first.",
            )
            return None

    @staticmethod
    def _base_context(profile, upload_form=None, analysis_form=None):
        papers = PreviousYearPaper.objects.filter(student=profile)
        return {
            "upload_form": upload_form or PreviousYearPaperUploadForm(),
            "analysis_form": analysis_form or PreviousYearAnalysisForm(
                student_profile=profile,
            ),
            "papers": papers,
            "has_papers": papers.exists(),
        }

    @staticmethod
    def _cache_extraction(paper):
        try:
            text = AIService.extract_pdf_text(paper.pdf, max_chars=100000)
        except Exception:
            logger.exception("Previous-year PDF extraction failed for paper_id=%s", paper.pk)
            text = ""
        paper.extracted_text = text
        paper.extracted_questions = PreviousYearAnalysisService.extract_questions(text)
        if not text.strip():
            paper.extraction_error = (
                "This PDF has no extractable text. Please upload a text-readable PDF."
            )
        elif not paper.extracted_questions:
            paper.extraction_error = (
                "No numbered questions could be read from this PDF. Please check the file."
            )
        else:
            paper.extraction_error = ""
        paper.save(update_fields=["extracted_text", "extracted_questions", "extraction_error"])

    @staticmethod
    def _map_unit(student_profile, subject, question):
        try:
            chunks = RAGService().search_relevant_chunks(
                student_profile,
                question,
                top_k=3,
                subject=subject,
            )
        except Exception:
            logger.info("Unable to map previous-year question to a note unit")
            return None
        units = [
            chunk.get("metadata", {}).get("unit", "").strip()
            for chunk in chunks
        ]
        units = [unit for unit in units if unit]
        if not units:
            return None
        most_common = max(set(units), key=units.count)
        if units.count(most_common) >= 2:
            return most_common
        return None


class ExamModeView(LoginRequiredMixin, View):
    """Build a last-day plan from the current student's note and paper evidence."""

    template_name = "ai_assistant/exam_mode.html"
    login_url = reverse_lazy("accounts:login")

    def get(self, request, *args, **kwargs):
        profile = self._get_student_profile(request)
        if profile is None:
            return redirect("dashboard:dashboard")
        return render(request, self.template_name, self._context(profile))

    def post(self, request, *args, **kwargs):
        profile = self._get_student_profile(request)
        if profile is None:
            return redirect("dashboard:dashboard")

        form = ExamModeForm(request.POST, student_profile=profile)
        context = self._context(profile, form=form)
        if not form.is_valid():
            return render(request, self.template_name, context)

        subject = form.cleaned_data["subject"]
        try:
            chunks = RAGService().search_relevant_chunks(
                profile,
                f"Core concepts, important topics, definitions, architectures, processes, and revision questions for {subject}",
                top_k=20,
                subject=subject,
            )
        except Exception:
            logger.exception(
                "Exam mode RAG retrieval failed for student_id=%s subject=%s",
                profile.pk,
                subject,
            )
            context["generation_error"] = (
                "Your uploaded notes could not be searched right now. Please try again."
            )
            return render(request, self.template_name, context)

        if not chunks:
            context["generation_error"] = (
                "No readable uploaded notes were found for this subject. Upload notes before creating a plan."
            )
            return render(request, self.template_name, context)

        papers = list(
            PreviousYearPaper.objects.filter(
                student=profile,
                subject=subject,
                extraction_error="",
            ).order_by("-year", "-uploaded_at")
        )
        previous_analysis = {}
        if papers:
            try:
                previous_analysis = PreviousYearAnalysisService.analyze(papers)
            except Exception:
                logger.exception(
                    "Previous-year data could not be included in exam mode for student_id=%s",
                    profile.pk,
                )

        try:
            plan = ExamModePlanner().build_plan(
                subject=subject,
                hours=form.cleaned_data["resolved_hours"],
                confidence=form.cleaned_data["confidence"],
                note_chunks=chunks,
                previous_analysis=previous_analysis,
                exam_date=form.cleaned_data["exam_date"],
            )
        except Exception:
            logger.exception("Exam mode plan generation failed for student_id=%s", profile.pk)
            context["generation_error"] = (
                "The revision plan could not be generated right now. Please try again."
            )
            return render(request, self.template_name, context)

        context.update({
            "plan": plan,
            "exam_date_warning": getattr(form, "add_warning", False),
            "selected_subject": subject,
        })
        return render(request, self.template_name, context)

    @staticmethod
    def _get_student_profile(request):
        try:
            return StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            messages.error(
                request,
                "Student profile not found. Please complete your profile first.",
            )
            return None

    @staticmethod
    def _context(profile, form=None):
        return {
            "form": form or ExamModeForm(student_profile=profile),
            "has_notes": Notes.objects.filter(student=profile).exists(),
        }
