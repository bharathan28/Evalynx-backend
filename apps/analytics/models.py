"""
Result model.

Aggregated analytics for a completed (or cancelled) interview.
Computed once and stored permanently for history retrieval.
"""

import uuid

from django.db import models

from apps.interviews.models import Interview


class Result(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.OneToOneField(
        Interview, on_delete=models.CASCADE, related_name="result"
    )

    # Aggregated scores (0–10)
    overall_score = models.FloatField(null=True, blank=True)
    technical_score = models.FloatField(null=True, blank=True)
    grammar_score = models.FloatField(null=True, blank=True)
    communication_score = models.FloatField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    completeness_score = models.FloatField(null=True, blank=True)

    # Aggregate filler counts
    total_filler_count = models.PositiveIntegerField(default=0)

    # Qualitative insights
    weak_areas = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "results"

    def __str__(self) -> str:
        return f"Result({self.interview_id}, score={self.overall_score})"
