from django.contrib import admin
from .models import Notes


@admin.register(Notes)
class NotesAdmin(admin.ModelAdmin):
    list_display = ("subject", "student", "semester", "unit", "uploaded_at")
    list_filter = ("semester", "unit", "uploaded_at")
    search_fields = (
        "subject",
        "student__user__first_name",
        "student__user__last_name",
        "student__user__email",
    )
    readonly_fields = ("uploaded_at", "updated_at")
    ordering = ("-uploaded_at",)
