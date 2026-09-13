from django.db import models

from accounts.models import StudentProfile


SEMESTER_CHOICES = [
    (str(number), f"Semester {number}") for number in range(1, 9)
]

EXAM_TYPE_CHOICES = [
    ("regular", "Regular"),
    ("makeup", "Make-up"),
    ("supplementary", "Supplementary"),
    ("other", "Other"),
]


class AIConversation(models.Model):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=200, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class AIMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        preview = self.content[:40].strip()
        if len(self.content) > 40:
            preview = f"{preview}..."
        return f"{self.get_role_display()}: {preview}"


class PreviousYearPaper(models.Model):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="previous_year_papers",
    )
    subject = models.CharField(max_length=100)
    semester = models.CharField(max_length=1, choices=SEMESTER_CHOICES)
    year = models.PositiveSmallIntegerField()
    exam_type = models.CharField(
        max_length=20,
        choices=EXAM_TYPE_CHOICES,
        default="regular",
    )
    pdf = models.FileField(upload_to="previous_year_papers/")
    extracted_text = models.TextField(blank=True)
    extracted_questions = models.JSONField(default=list, blank=True)
    extraction_error = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-uploaded_at"]
        indexes = [
            models.Index(
                fields=["student", "subject", "year"],
                name="ai_assistan_student_4d9a5f_idx",
            ),
        ]

    def __str__(self):
        return f"{self.subject} - {self.year} - {self.get_exam_type_display()}"

    def delete(self, *args, **kwargs):
        storage = self.pdf.storage
        pdf_name = self.pdf.name
        super().delete(*args, **kwargs)
        if pdf_name and storage.exists(pdf_name):
            storage.delete(pdf_name)
