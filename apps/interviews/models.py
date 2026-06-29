"""
Interview domain models.

Interview  — a single assessment session
Question   — one AI-generated question within an interview
Answer     — the candidate's response with all computed scores
"""

import uuid

from django.db import models

from apps.authentication.models import User


class InterviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Interview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="interviews"
    )
    job_description = models.TextField()
    question_count = models.PositiveSmallIntegerField(default=5)
    completed_questions = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=InterviewStatus.choices,
        default=InterviewStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interviews"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Interview({self.user.email}, {self.status})"

    @property
    def is_complete(self) -> bool:
        return self.status == InterviewStatus.COMPLETED

    def advance(self) -> None:
        """Increment answered question count and check for completion."""
        self.completed_questions += 1
        if self.completed_questions >= self.question_count:
            self.status = InterviewStatus.COMPLETED
        self.save(update_fields=["completed_questions", "status", "updated_at"])


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(
        Interview, on_delete=models.CASCADE, related_name="questions"
    )
    question_text = models.TextField()
    question_number = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "questions"
        ordering = ["question_number"]
        unique_together = [("interview", "question_number")]

    def __str__(self) -> str:
        return f"Q{self.question_number} — {self.interview_id}"


class Answer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name="answer"
    )

    # Transcription
    transcript = models.TextField(blank=True)

    # Scores (0–10 scale, stored as floats for precision)
    technical_score = models.FloatField(null=True, blank=True)
    grammar_score = models.FloatField(null=True, blank=True)
    communication_score = models.FloatField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    completeness_score = models.FloatField(null=True, blank=True)

    # Filler words
    filler_count = models.PositiveIntegerField(default=0)
    filler_details = models.JSONField(default=dict)  # {"umm": 3, "like": 5}

    # AI feedback
    feedback = models.TextField(blank=True)
    better_answer = models.TextField(blank=True)
    missing_concepts = models.JSONField(default=list)
    mistakes = models.JSONField(default=list)

    # Grammar
    grammar_mistakes_count = models.PositiveIntegerField(default=0)
    grammar_suggestions = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "answers"

    def __str__(self) -> str:
        return f"Answer({self.question_id})"

    @property
    def overall_score(self) -> float | None:
        scores = [
            self.technical_score,
            self.grammar_score,
            self.communication_score,
            self.confidence_score,
            self.completeness_score,
        ]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None
