from django.contrib import admin

from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "branch", "semester", "created_at")
    search_fields = ("full_name", "user__email", "user__username")
    list_filter = ("branch", "semester", "created_at")
    ordering = ("full_name",)
