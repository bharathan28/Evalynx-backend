"""
Analytics service.

Aggregates individual answer scores into a single Result record.
Called automatically when an interview ends (complete or cancelled).
"""

from __future__ import annotations

import logging
import uuid

from apps.authentication.models import User
from apps.interviews.models import Interview

from .models import Result

logger = logging.getLogger(__name__)


class AnalyticsService:

    @staticmethod
    def generate_result(interview: Interview) -> Result:
        """
        Compute aggregated scores from all answered questions and
        upsert a Result record. Safe to call multiple times (idempotent).
        """
        answers = [
            q.answer
            for q in interview.questions.prefetch_related("answer").all()
            if hasattr(q, "answer")
        ]

        if not answers:
            result, _ = Result.objects.get_or_create(interview=interview)
            return result

        def avg(field: str) -> float | None:
            values = [getattr(a, field) for a in answers if getattr(a, field) is not None]
            return round(sum(values) / len(values), 2) if values else None

        technical_score = avg("technical_score")
        grammar_score = avg("grammar_score")
        communication_score = avg("communication_score")
        confidence_score = avg("confidence_score")
        completeness_score = avg("completeness_score")
        total_filler_count = sum(a.filler_count for a in answers)

        all_scores = [s for s in [
            technical_score, grammar_score, communication_score,
            confidence_score, completeness_score,
        ] if s is not None]
        overall_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else None

        weak_areas = AnalyticsService._identify_weak_areas(
            technical_score, grammar_score, communication_score,
            confidence_score, completeness_score, total_filler_count,
        )
        recommendations = AnalyticsService._build_recommendations(weak_areas, answers)

        result, _ = Result.objects.update_or_create(
            interview=interview,
            defaults={
                "overall_score": overall_score,
                "technical_score": technical_score,
                "grammar_score": grammar_score,
                "communication_score": communication_score,
                "confidence_score": confidence_score,
                "completeness_score": completeness_score,
                "total_filler_count": total_filler_count,
                "weak_areas": weak_areas,
                "recommendations": recommendations,
            },
        )

        logger.info("Result generated for interview %s — overall: %s", interview.id, overall_score)
        return result

    @staticmethod
    def get_or_generate_result(interview_id: uuid.UUID, user: User) -> Result:
        try:
            interview = Interview.objects.get(id=interview_id, user=user)
        except Interview.DoesNotExist:
            raise ValueError("Interview not found.")

        if hasattr(interview, "result"):
            return interview.result

        return AnalyticsService.generate_result(interview)

    @staticmethod
    def get_user_history(user: User) -> list[Result]:
        return (
            Result.objects
            .filter(interview__user=user)
            .select_related("interview")
            .order_by("-created_at")
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _identify_weak_areas(
        technical: float | None,
        grammar: float | None,
        communication: float | None,
        confidence: float | None,
        completeness: float | None,
        filler_count: int,
    ) -> list[str]:
        THRESHOLD = 6.0
        areas = []
        if technical is not None and technical < THRESHOLD:
            areas.append("Technical depth and accuracy")
        if grammar is not None and grammar < THRESHOLD:
            areas.append("Grammar and language quality")
        if communication is not None and communication < THRESHOLD:
            areas.append("Communication clarity")
        if confidence is not None and confidence < THRESHOLD:
            areas.append("Confidence and delivery")
        if completeness is not None and completeness < THRESHOLD:
            areas.append("Answer completeness")
        if filler_count > 10:
            areas.append("Excessive use of filler words")
        return areas

    @staticmethod
    def _build_recommendations(weak_areas: list[str], answers: list) -> list[str]:
        """Generate actionable improvement suggestions from weak areas."""
        recs = []
        mapping = {
            "Technical depth and accuracy": (
                "Study the core concepts highlighted in missed answers. "
                "Practice with LeetCode / system design challenges."
            ),
            "Grammar and language quality": (
                "Review technical writing fundamentals. "
                "Use tools like Grammarly when practising written answers."
            ),
            "Communication clarity": (
                "Practise the STAR method (Situation, Task, Action, Result) "
                "to structure answers clearly."
            ),
            "Confidence and delivery": (
                "Record yourself answering questions and review the playback. "
                "Slow down — clarity matters more than speed."
            ),
            "Answer completeness": (
                "Always cover the Why, What, and How in each answer. "
                "Don't skip examples from your own experience."
            ),
            "Excessive use of filler words": (
                "Pause intentionally instead of filling silence with 'umm' or 'like'. "
                "Silence signals confidence."
            ),
        }
        for area in weak_areas:
            if area in mapping:
                recs.append(mapping[area])

        # Collect top recurring missing concepts across all answers
        concept_freq: dict[str, int] = {}
        for answer in answers:
            for concept in answer.missing_concepts:
                concept_freq[concept] = concept_freq.get(concept, 0) + 1

        top_concepts = sorted(concept_freq, key=lambda c: -concept_freq[c])[:3]
        if top_concepts:
            recs.append(
                f"Focus on strengthening your understanding of: {', '.join(top_concepts)}."
            )

        return recs
