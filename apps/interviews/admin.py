from django.contrib import admin
from .models import Answer, Interview, Question

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    readonly_fields = ("question_number", "question_text")

@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "question_count", "completed_questions", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [QuestionInline]

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("question", "technical_score", "grammar_score", "confidence_score", "overall_score")
    readonly_fields = ("created_at",)
