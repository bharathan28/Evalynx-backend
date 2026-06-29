from django.contrib import admin
from .models import Result

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("interview", "overall_score", "technical_score", "confidence_score", "created_at")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("interview__user__email",)
