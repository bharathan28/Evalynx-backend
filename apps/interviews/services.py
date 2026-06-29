"""
Interview service layer.

Orchestrates the full answer-processing pipeline:
  video → audio extraction → transcription → local processing → AI evaluation
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from django.conf import settings

from apps.authentication.models import User
from services.ai.question_generator import QuestionGeneratorService
from services.ai.technical_evaluator import TechnicalEvaluatorService
from services.processors.confidence_score import ConfidenceScoreService
from services.processors.filler_detector import FillerDetectorService
from services.processors.grammar_checker import GrammarCheckerService
from services.processors.speech_to_text import SpeechToTextService

from .models import Answer, Interview, InterviewStatus, Question

logger = logging.getLogger(__name__)


class InterviewService:

    @staticmethod
    def start_interview(user: User, job_description: str, question_count: int) -> tuple[Interview, list[Question]]:
        """
        Create an Interview record, generate AI questions, persist them,
        and return the interview + ordered question list.
        """
        # Retrieve the user's profile to enrich question generation
        try:
            profile = user.profile
            profile_summary = {
                "skills": profile.skills,
                "experience": profile.experience,
                "education": profile.education,
                "projects": profile.projects,
                "certifications": profile.certifications,
            }
        except Exception:
            profile_summary = {}

        interview = Interview.objects.create(
            user=user,
            job_description=job_description,
            question_count=question_count,
            status=InterviewStatus.ACTIVE,
        )

        raw_questions = QuestionGeneratorService.generate(
            profile=profile_summary,
            job_description=job_description,
            count=question_count,
        )

        questions = [
            Question(
                interview=interview,
                question_text=text,
                question_number=idx + 1,
            )
            for idx, text in enumerate(raw_questions)
        ]
        Question.objects.bulk_create(questions)
        questions = list(interview.questions.order_by("question_number"))

        logger.info("Interview %s started with %d questions", interview.id, len(questions))
        return interview, questions

    @staticmethod
    def get_question(interview_id: uuid.UUID, question_number: int, user: User) -> Question:
        interview = InterviewService._get_active_interview(interview_id, user)
        try:
            return interview.questions.get(question_number=question_number)
        except Question.DoesNotExist:
            raise ValueError(f"Question {question_number} does not exist in this interview.")

    @staticmethod
    def submit_answer(
        interview_id: uuid.UUID,
        question_number: int,
        user: User,
        video_file=None,
        transcript_override: str = "",
    ) -> Answer:
        """
        Process a submitted answer through the full pipeline and persist scores.
        Video (if provided) is deleted immediately after transcription.
        """
        interview = InterviewService._get_active_interview(interview_id, user)
        question = InterviewService.get_question(interview_id, question_number, user)

        # ── Step 1: Transcription ───────────────────────────────────────────────
        if transcript_override:
            transcript = transcript_override
            audio_metadata = {}
        else:
            transcript, audio_metadata = InterviewService._process_video(video_file)

        # ── Step 2: Local processing (no API cost) ─────────────────────────────
        grammar_result = GrammarCheckerService.check(transcript)
        filler_result = FillerDetectorService.detect(transcript)
        confidence_result = ConfidenceScoreService.compute(
            transcript=transcript,
            audio_metadata=audio_metadata,
            filler_count=filler_result["total_count"],
        )

        # ── Step 3: AI evaluation (single API call per answer) ─────────────────
        ai_result = TechnicalEvaluatorService.evaluate(
            question=question.question_text,
            transcript=transcript,
        )

        # ── Step 4: Persist ────────────────────────────────────────────────────
        answer = Answer.objects.create(
            question=question,
            transcript=transcript,
            technical_score=ai_result.get("technical_score"),
            grammar_score=grammar_result.get("grammar_score"),
            communication_score=confidence_result.get("communication_score"),
            confidence_score=confidence_result.get("confidence_score"),
            completeness_score=ai_result.get("completeness_score"),
            filler_count=filler_result["total_count"],
            filler_details=filler_result["details"],
            feedback=ai_result.get("feedback", ""),
            better_answer=ai_result.get("better_answer", ""),
            missing_concepts=ai_result.get("missing_concepts", []),
            mistakes=ai_result.get("mistakes", []),
            grammar_mistakes_count=grammar_result.get("mistake_count", 0),
            grammar_suggestions=grammar_result.get("suggestions", []),
        )

        interview.advance()
        logger.info("Answer submitted for Q%d in interview %s", question_number, interview_id)
        return answer

    @staticmethod
    def cancel_interview(interview_id: uuid.UUID, user: User) -> Interview:
        interview = InterviewService._get_active_interview(interview_id, user)
        interview.status = InterviewStatus.CANCELLED
        interview.save(update_fields=["status", "updated_at"])

        # Trigger analytics generation for partial results
        from apps.analytics.services import AnalyticsService
        AnalyticsService.generate_result(interview)

        logger.info("Interview %s cancelled after %d questions", interview_id, interview.completed_questions)
        return interview

    @staticmethod
    def _process_video(video_file) -> tuple[str, dict]:
        """
        Save video to a temp file, extract audio, transcribe, then delete.
        Returns (transcript, audio_metadata).
        """
        tmp_video_path: str | None = None
        try:
            suffix = ".webm"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir="/tmp") as tmp:
                tmp_video_path = tmp.name
                for chunk in video_file.chunks():
                    tmp.write(chunk)

            transcript, metadata = SpeechToTextService.transcribe(tmp_video_path)
            return transcript, metadata
        finally:
            if tmp_video_path and os.path.exists(tmp_video_path):
                os.remove(tmp_video_path)
                logger.debug("Temp video deleted: %s", tmp_video_path)

    @staticmethod
    def _get_active_interview(interview_id: uuid.UUID, user: User) -> Interview:
        try:
            interview = Interview.objects.get(id=interview_id, user=user)
        except Interview.DoesNotExist:
            raise ValueError("Interview not found.")
        if interview.status not in (InterviewStatus.ACTIVE,):
            raise ValueError(
                f"Interview is not active (current status: {interview.status})."
            )
        return interview

    @staticmethod
    def get_history(user: User) -> list[Interview]:
        return (
            Interview.objects
            .filter(user=user)
            .exclude(status=InterviewStatus.PENDING)
            .order_by("-created_at")
        )
