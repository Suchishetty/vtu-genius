from django.db import models
from django.contrib.auth.models import User


class StudentProfile(models.Model):
    """
    Student Profile model that extends Django's built-in User model.
    Each user can have one student profile with academic and personal information.
    """
    
    BRANCH_CHOICES = [
        ('CSE', 'CSE'),
        ('ISE', 'ISE'),
        ('AIML', 'AIML'),
        ('AIDS', 'AIDS'),
        ('ECE', 'ECE'),
        ('EEE', 'EEE'),
        ('Mechanical', 'Mechanical'),
        ('Civil', 'Civil'),
        ('Other', 'Other'),
    ]
    
    SEMESTER_CHOICES = [
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ]
    
    # Link to Django User model - one-to-one relationship
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Student's full name
    full_name = models.CharField(max_length=255)
    
    # Unique email address
    email = models.EmailField(unique=True)
    
    # Branch/Department
    branch = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    
    # Current semester
    semester = models.CharField(max_length=50, choices=SEMESTER_CHOICES)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['full_name']
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
    
    def __str__(self):
        return f"{self.full_name} ({self.branch} - {self.semester})"
