from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("ai_assistant", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PreviousYearPaper",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=100)),
                ("semester", models.CharField(choices=[("1", "Semester 1"), ("2", "Semester 2"), ("3", "Semester 3"), ("4", "Semester 4"), ("5", "Semester 5"), ("6", "Semester 6"), ("7", "Semester 7"), ("8", "Semester 8")], max_length=1)),
                ("year", models.PositiveSmallIntegerField()),
                ("exam_type", models.CharField(choices=[("regular", "Regular"), ("makeup", "Make-up"), ("supplementary", "Supplementary"), ("other", "Other")], default="regular", max_length=20)),
                ("pdf", models.FileField(upload_to="previous_year_papers/")),
                ("extracted_text", models.TextField(blank=True)),
                ("extracted_questions", models.JSONField(blank=True, default=list)),
                ("extraction_error", models.CharField(blank=True, max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="previous_year_papers", to="accounts.studentprofile")),
            ],
            options={
                "ordering": ["-year", "-uploaded_at"],
                "indexes": [models.Index(fields=["student", "subject", "year"], name="ai_assistan_student_4d9a5f_idx")],
            },
        ),
    ]
