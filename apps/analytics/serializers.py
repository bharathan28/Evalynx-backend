from rest_framework import serializers

from apps.interviews.serializers import InterviewDetailSerializer

from .models import Result


class ResultSerializer(serializers.ModelSerializer):
    interview = InterviewDetailSerializer(read_only=True)

    class Meta:
        model = Result
        fields = (
            "id",
            "interview",
            "overall_score",
            "technical_score",
            "grammar_score",
            "communication_score",
            "confidence_score",
            "completeness_score",
            "total_filler_count",
            "weak_areas",
            "recommendations",
            "created_at",
        )
        read_only_fields = fields


class ResultSummarySerializer(serializers.ModelSerializer):
    """Lightweight version used in the history list."""

    job_description = serializers.CharField(source="interview.job_description", read_only=True)
    interview_status = serializers.CharField(source="interview.status", read_only=True)
    interview_date = serializers.DateTimeField(source="interview.created_at", read_only=True)
    completed_questions = serializers.IntegerField(
        source="interview.completed_questions", read_only=True
    )
    question_count = serializers.IntegerField(source="interview.question_count", read_only=True)

    class Meta:
        model = Result
        fields = (
            "id",
            "interview_id",
            "job_description",
            "interview_status",
            "interview_date",
            "completed_questions",
            "question_count",
            "overall_score",
            "technical_score",
            "weak_areas",
        )
