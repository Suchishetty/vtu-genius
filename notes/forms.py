from django import forms
from .models import Notes


class UploadNotesForm(forms.ModelForm):
    class Meta:
        model = Notes
        fields = ["subject", "semester", "unit", "pdf", "description"]
        widgets = {
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter subject name"
            }),
            "semester": forms.Select(attrs={
                "class": "form-select"
            }),
            "unit": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: Unit 1"
            }),
            "pdf": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": ".pdf,application/pdf"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "placeholder": "Brief description of the notes (optional)",
                "rows": 4
            }),
        }

    def clean_pdf(self):
        pdf = self.cleaned_data.get("pdf")

        if pdf:
            if not pdf.name.lower().endswith(".pdf"):
                raise forms.ValidationError("Only PDF files are allowed.")

            if hasattr(pdf, "content_type") and pdf.content_type:
                if pdf.content_type != "application/pdf":
                    raise forms.ValidationError("Only PDF files are allowed.")

            header = pdf.read(4)
            pdf.seek(0)
            if header != b"%PDF":
                raise forms.ValidationError("Only PDF files are allowed.")

        return pdf
