from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    """
    Admin configuration for StudentProfile model.
    Provides a clean, organized interface for managing student profiles.
    """
    
    list_display = (
        "full_name",
        "email",
        "branch",
        "semester",
        "created_at",
    )
    
    list_filter = (
        "branch",
        "semester",
    )
    
    search_fields = (
        "full_name",
        "email",
    )
    
    ordering = (
        "full_name",
    )
    
    readonly_fields = (
        "created_at",
        "updated_at",
    )
