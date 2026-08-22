from django.db import models
from accounts.models import StudentProfile


SEMESTER_CHOICES = [
    ("1", "Semester 1"),
    ("2", "Semester 2"),
    ("3", "Semester 3"),
    ("4", "Semester 4"),
    ("5", "Semester 5"),
    ("6", "Semester 6"),
    ("7", "Semester 7"),
    ("8", "Semester 8"),
]


class Notes(models.Model):
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="notes"
    )
    subject = models.CharField(max_length=100)
    semester = models.CharField(max_length=1, choices=SEMESTER_CHOICES)
    unit = models.CharField(max_length=50)
    pdf = models.FileField(upload_to="notes/pdfs/")
    description = models.TextField(blank=True, max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Note"
        verbose_name_plural = "Notes"

    def __str__(self):
        return f"{self.subject} - {self.semester} - {self.unit}"

    def delete(self, *args, **kwargs):
        storage = self.pdf.storage
        pdf_name = self.pdf.name
        super().delete(*args, **kwargs)
        if pdf_name and storage.exists(pdf_name):
            storage.delete(pdf_name)
