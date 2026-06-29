from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "resume_parsed_at", "is_complete")
    search_fields = ("user__email", "full_name")
    readonly_fields = ("resume_parsed_at", "created_at", "updated_at")
