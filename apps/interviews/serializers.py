from rest_framework import serializers

from .models import Answer, Interview, Question


class StartInterviewSerializer(serializers.Serializer):
    job_description = serializers.CharField(min_length=20, max_length=5000)
    question_count = serializers.IntegerField(min_value=1, max_value=20, default=5)


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ("id", "question_text", "question_number")


class SubmitAnswerSerializer(serializers.Serializer):
    interview_id = serializers.UUIDField()
    question_number = serializers.IntegerField(min_value=1)
    video = serializers.FileField(required=False)
    # Allow text-only submission (useful for testing / text-mode)
    transcript_override = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("video") and not attrs.get("transcript_override"):
            raise serializers.ValidationError(
                "Either a video file or a transcript_override must be provided."
            )
        return attrs


class AnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.question_text", read_only=True)
    question_number = serializers.IntegerField(source="question.question_number", read_only=True)
    overall_score = serializers.FloatField(read_only=True)

    class Meta:
        model = Answer
        fields = (
            "id",
            "question_text",
            "question_number",
            "transcript",
            "technical_score",
            "grammar_score",
            "communication_score",
            "confidence_score",
            "completeness_score",
            "overall_score",
            "filler_count",
            "filler_details",
            "feedback",
            "better_answer",
            "missing_concepts",
            "mistakes",
            "grammar_mistakes_count",
            "grammar_suggestions",
        )


class InterviewSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for history list views."""

    class Meta:
        model = Interview
        fields = (
            "id",
            "job_description",
            "question_count",
            "completed_questions",
            "status",
            "created_at",
        )


class InterviewDetailSerializer(serializers.ModelSerializer):
    """Full interview detail including all questions and answers."""

    questions = serializers.SerializerMethodField()

    class Meta:
        model = Interview
        fields = (
            "id",
            "job_description",
            "question_count",
            "completed_questions",
            "status",
            "questions",
            "created_at",
        )

    def get_questions(self, obj: Interview) -> list:
        questions = obj.questions.prefetch_related("answer").all()
        result = []
        for q in questions:
            q_data = QuestionSerializer(q).data
            if hasattr(q, "answer"):
                q_data["answer"] = AnswerSerializer(q.answer).data
            else:
                q_data["answer"] = None
            result.append(q_data)
        return result
