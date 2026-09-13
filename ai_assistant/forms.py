from datetime import date, timedelta

from django import forms

from notes.models import Notes

from .models import EXAM_TYPE_CHOICES, PreviousYearPaper, SEMESTER_CHOICES


class QuestionGeneratorForm(forms.Form):
    """Student-scoped controls for generating questions from one indexed note."""

    subject = forms.ChoiceField(label="Subject")
    unit = forms.ChoiceField(label="Unit")
    note = forms.ModelChoiceField(label="Uploaded note", queryset=Notes.objects.none())
    marks = forms.ChoiceField(
        label="Marks",
        choices=[("2", "2 marks"), ("5", "5 marks"), ("10", "10 marks"),
                 ("15", "15 marks"), ("20", "20 marks")],
    )
    question_count = forms.ChoiceField(
        label="Number of questions",
        choices=[(str(number), str(number)) for number in range(1, 11)],
        initial="5",
    )

    def __init__(self, *args, student_profile, **kwargs):
        super().__init__(*args, **kwargs)
        notes = Notes.objects.filter(student=student_profile).order_by(
            "subject", "unit", "-uploaded_at"
        )
        self.fields["note"].queryset = notes
        self.fields["subject"].choices = [
            (subject, subject)
            for subject in notes.values_list("subject", flat=True).distinct()
        ]
        self.fields["unit"].choices = [
            (unit, unit)
            for unit in notes.values_list("unit", flat=True).distinct()
        ]

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned_data = super().clean()
        note = cleaned_data.get("note")
        subject = cleaned_data.get("subject")
        unit = cleaned_data.get("unit")

        if note and (note.subject != subject or note.unit != unit):
            raise forms.ValidationError(
                "Select a note that matches the selected subject and unit."
            )

        return cleaned_data


class ExpectedQuestionsForm(forms.Form):
    subject = forms.ChoiceField(label="Subject")
    unit = forms.ChoiceField(label="Unit")
    marks = forms.ChoiceField(
        label="Marks",
        choices=[
            ("all", "All Marks"),
            ("2", "2 Marks"),
            ("5", "5 Marks"),
            ("10", "10 Marks"),
            ("15", "15 Marks"),
            ("20", "20 Marks"),
        ],
    )
    question_count = forms.ChoiceField(
        label="Number of expected questions",
        choices=[("5", "5"), ("10", "10"), ("15", "15")],
        initial="5",
    )

    def __init__(self, *args, student_profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_profile = student_profile
        notes = Notes.objects.filter(student=student_profile).order_by(
            "subject", "unit"
        )
        subjects = list(notes.values_list("subject", flat=True).distinct())
        self.fields["subject"].choices = [(subject, subject) for subject in subjects]
        self.fields["unit"].choices = [("all", "All Units")]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"

        selected_subject = self.data.get("subject") if self.is_bound else None
        if selected_subject in subjects:
            units = notes.filter(subject=selected_subject).values_list(
                "unit", flat=True
            ).distinct()
            self.fields["unit"].choices += [(unit, unit) for unit in units]
        elif not self.is_bound:
            units = notes.values_list("unit", flat=True).distinct()
            self.fields["unit"].choices += [(unit, unit) for unit in units]

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get("subject")
        unit = cleaned_data.get("unit")
        notes = Notes.objects.filter(student=self.student_profile, subject=subject)
        if not notes.exists():
            raise forms.ValidationError("Select a subject from your uploaded notes.")
        if unit != "all" and not notes.filter(unit=unit).exists():
            raise forms.ValidationError("Select a unit from the selected subject.")
        return cleaned_data


class PreviousYearPaperUploadForm(forms.ModelForm):
    class Meta:
        model = PreviousYearPaper
        fields = ["subject", "semester", "year", "exam_type", "pdf"]
        widgets = {
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter subject name",
            }),
            "semester": forms.Select(
                choices=SEMESTER_CHOICES,
                attrs={"class": "form-select"},
            ),
            "year": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 1900,
                "max": date.today().year + 1,
                "placeholder": "Example: 2025",
            }),
            "exam_type": forms.Select(
                choices=EXAM_TYPE_CHOICES,
                attrs={"class": "form-select"},
            ),
            "pdf": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": ".pdf,application/pdf",
            }),
        }

    def clean_subject(self):
        subject = self.cleaned_data["subject"].strip()
        if not subject:
            raise forms.ValidationError("Subject is required.")
        return subject

    def clean_year(self):
        year = self.cleaned_data["year"]
        if year < 1900 or year > date.today().year + 1:
            raise forms.ValidationError("Enter a valid exam year.")
        return year

    def clean_pdf(self):
        pdf = self.cleaned_data.get("pdf")
        if not pdf:
            raise forms.ValidationError("Upload a question-paper PDF.")
        if pdf.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Question papers must be 10 MB or smaller.")
        if not pdf.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Only PDF files are allowed.")
        content_type = getattr(pdf, "content_type", "")
        if content_type and content_type != "application/pdf":
            raise forms.ValidationError("Only PDF files are allowed.")
        header = pdf.read(4)
        pdf.seek(0)
        if header != b"%PDF":
            raise forms.ValidationError("Only PDF files are allowed.")
        return pdf


class PreviousYearAnalysisForm(forms.Form):
    subject = forms.ChoiceField(label="Subject")
    year_from = forms.IntegerField(
        label="From year",
        required=False,
        min_value=1900,
        max_value=date.today().year + 1,
    )
    year_to = forms.IntegerField(
        label="To year",
        required=False,
        min_value=1900,
        max_value=date.today().year + 1,
    )
    paper_count = forms.ChoiceField(
        label="Number of papers",
        choices=[("all", "All matching papers"), ("3", "3"), ("5", "5"), ("10", "10")],
        initial="all",
    )

    def __init__(self, *args, student_profile, **kwargs):
        super().__init__(*args, **kwargs)
        subjects = PreviousYearPaper.objects.filter(
            student=student_profile,
        ).values_list("subject", flat=True).distinct()
        self.fields["subject"].choices = [(subject, subject) for subject in subjects]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["paper_count"].widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned_data = super().clean()
        year_from = cleaned_data.get("year_from")
        year_to = cleaned_data.get("year_to")
        if year_from and year_to and year_from > year_to:
            raise forms.ValidationError("The start year cannot be after the end year.")
        return cleaned_data


class ExamModeForm(forms.Form):
    subject = forms.ChoiceField(label="Subject")
    exam_date = forms.DateField(
        label="Exam date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    study_hours = forms.ChoiceField(
        label="Available study time",
        choices=[
            ("2", "2 hours"),
            ("4", "4 hours"),
            ("6", "6 hours"),
            ("8", "8 hours"),
            ("10", "10 hours"),
            ("custom", "Custom"),
        ],
    )
    custom_hours = forms.DecimalField(
        label="Custom hours",
        required=False,
        min_value=0.5,
        max_value=24,
        decimal_places=1,
        max_digits=3,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": "0.5",
            "max": "24",
            "step": "0.5",
            "placeholder": "Example: 3.5",
        }),
    )
    confidence = forms.ChoiceField(
        label="How confident are you?",
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        initial="medium",
    )

    def __init__(self, *args, student_profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_profile = student_profile
        subjects = Notes.objects.filter(student=student_profile).values_list(
            "subject", flat=True
        ).distinct()
        self.fields["subject"].choices = [(subject, subject) for subject in subjects]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select")

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get("subject")
        exam_date = cleaned_data.get("exam_date")
        study_hours = cleaned_data.get("study_hours")
        custom_hours = cleaned_data.get("custom_hours")

        if not Notes.objects.filter(student=self.student_profile, subject=subject).exists():
            raise forms.ValidationError("Select a subject from your uploaded notes.")
        if exam_date:
            today = date.today()
            if exam_date < today:
                raise forms.ValidationError("The exam date cannot be in the past.")
            if exam_date > today + timedelta(days=3):
                self.add_warning = True
        if study_hours == "custom" and custom_hours is None:
            self.add_error("custom_hours", "Enter your available study time.")
        if study_hours != "custom" and study_hours:
            cleaned_data["resolved_hours"] = float(study_hours)
        elif custom_hours is not None:
            cleaned_data["resolved_hours"] = float(custom_hours)
        return cleaned_data
