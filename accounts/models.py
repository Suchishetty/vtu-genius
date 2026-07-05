from django.contrib.auth.models import User
from django.db import models


class StudentProfile(models.Model):
    BRANCH_CSE = "CSE"
    BRANCH_ISE = "ISE"
    BRANCH_AIML = "AIML"
    BRANCH_AIDS = "AIDS"
    BRANCH_ECE = "ECE"
    BRANCH_EEE = "EEE"
    BRANCH_MECHANICAL = "Mechanical"
    BRANCH_CIVIL = "Civil"
    BRANCH_OTHER = "Other"

    SEMESTER_1 = "Semester 1"
    SEMESTER_2 = "Semester 2"
    SEMESTER_3 = "Semester 3"
    SEMESTER_4 = "Semester 4"
    SEMESTER_5 = "Semester 5"
    SEMESTER_6 = "Semester 6"
    SEMESTER_7 = "Semester 7"
    SEMESTER_8 = "Semester 8"

    BRANCH_CHOICES = [
        (BRANCH_CSE, "CSE"),
        (BRANCH_ISE, "ISE"),
        (BRANCH_AIML, "AIML"),
        (BRANCH_AIDS, "AIDS"),
        (BRANCH_ECE, "ECE"),
        (BRANCH_EEE, "EEE"),
        (BRANCH_MECHANICAL, "Mechanical"),
        (BRANCH_CIVIL, "Civil"),
        (BRANCH_OTHER, "Other"),
    ]

    SEMESTER_CHOICES = [
        (SEMESTER_1, "Semester 1"),
        (SEMESTER_2, "Semester 2"),
        (SEMESTER_3, "Semester 3"),
        (SEMESTER_4, "Semester 4"),
        (SEMESTER_5, "Semester 5"),
        (SEMESTER_6, "Semester 6"),
        (SEMESTER_7, "Semester 7"),
        (SEMESTER_8, "Semester 8"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    branch = models.CharField(max_length=20, choices=BRANCH_CHOICES)
    semester = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"

    def __str__(self):
        return f"{self.full_name} ({self.branch} - {self.semester})"
