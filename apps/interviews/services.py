"""
Interview service layer.

Orchestrates the full answer-processing pipeline:
  video → audio extraction → transcription → local processing → AI evaluation

Key behaviour notes (read before modifying):
  - get_question() works for ACTIVE, COMPLETED, and CANCELLED interviews
    (read-only). This matters because the moment the LAST answer is
    submitted, interview.advance() flips status to COMPLETED. A frontend
    that still tries to fetch/skip "the next question" right after that
    must not get a hard 400 — it should be told plainly that the
    interview has finished.
  - submit_answer() and skip_question() still require an ACTIVE interview,
    since you can't modify a finished session. Both return the interview
    object alongside the answer so the view can tell the frontend exactly
    what to do next (go to results vs. continue) in a single response.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid

from apps.authentication.models import User
from services.ai.question_generator import QuestionGeneratorService
from services.ai.technical_evaluator import TechnicalEvaluatorService
from services.processors.confidence_score import ConfidenceScoreService
from services.processors.filler_detector import FillerDetectorService
from services.processors.grammar_checker import GrammarCheckerService
from services.processors.speech_to_text import SpeechToTextService

from .models import Answer, Interview, InterviewStatus, Question

logger = logging.getLogger(__name__)

# Interview statuses that allow read-only access (fetching/viewing questions)
READABLE_STATUSES = (
    InterviewStatus.ACTIVE,
    InterviewStatus.COMPLETED,
    InterviewStatus.CANCELLED,
)


class InterviewService:

    @staticmethod
    def start_interview(user: User, job_description: str, question_count: int) -> tuple[Interview, list[Question]]:
        """
        Create an Interview record, generate AI questions, persist them,
        and return the interview + ordered question list.
        """
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
        """
        Fetch a question. Works for ACTIVE, COMPLETED, and CANCELLED
        interviews — fetching/viewing a question is always safe, even
        after the session has ended.
        """
        interview = InterviewService._get_interview(interview_id, user, require_active=False)
        try:
            return interview.questions.get(question_number=question_number)
        except Question.DoesNotExist:
            raise ValueError(f"Question {question_number} does not exist in this interview.")

    @staticmethod
    def skip_question(interview_id: uuid.UUID, question_number: int, user: User) -> tuple[Answer, Interview]:
        """Mark a question as skipped. Requires an ACTIVE interview."""
        interview = InterviewService._get_interview(interview_id, user, require_active=True)
        question = interview.questions.filter(question_number=question_number).first()
        if question is None:
            raise ValueError(f"Question {question_number} does not exist in this interview.")

        if hasattr(question, "answer"):
            raise ValueError("This question has already been answered or skipped.")

        answer = Answer.objects.create(
            question=question,
            transcript="",
            is_skipped=True,
            technical_score=0.0,
            grammar_score=0.0,
            communication_score=0.0,
            confidence_score=0.0,
            completeness_score=0.0,
            filler_count=0,
            filler_details={},
            feedback="Candidate skipped this question.",
            better_answer="",
            missing_concepts=[],
            mistakes=["Question skipped"],
            grammar_mistakes_count=0,
            grammar_suggestions=[],
        )

        interview.advance()
        interview.refresh_from_db()

        logger.info("Question %d skipped — interview %s", question_number, interview_id)
        return answer, interview

    @staticmethod
    def submit_answer(
        interview_id: uuid.UUID,
        question_number: int,
        user: User,
        video_file=None,
        transcript_override: str = "",
    ) -> tuple[Answer, Interview]:
        """
        Process a submitted answer through the full pipeline and persist scores.
        Video (if provided) is deleted immediately after transcription.
        Requires an ACTIVE interview. Returns (answer, interview) so the
        caller can immediately tell whether this was the final question.
        """
        interview = InterviewService._get_interview(interview_id, user, require_active=True)
        question = interview.questions.filter(question_number=question_number).first()
        if question is None:
            raise ValueError(f"Question {question_number} does not exist in this interview.")

        if hasattr(question, "answer"):
            raise ValueError("This question has already been answered or skipped.")

        # ── Step 1: Transcription ───────────────────────────────────────────────
        if transcript_override:
            transcript = transcript_override
            audio_metadata = {}
        elif video_file:
            transcript, audio_metadata = InterviewService._process_video(video_file)
        else:
            raise ValueError("Either a video file or a transcript_override is required.")

        # ── Step 2: Local processing (no API cost) ─────────────────────────────
        grammar_result = GrammarCheckerService.check(transcript)
        filler_result = FillerDetectorService.detect(transcript)
        confidence_result = ConfidenceScoreService.compute(
            transcript=transcript,
            audio_metadata=audio_metadata,
            filler_count=filler_result["total_count"],
        )

        # ── Step 3: AI evaluation (single Gemini call per answer) ──────────────
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
        interview.refresh_from_db()

        logger.info("Answer submitted for Q%d in interview %s", question_number, interview_id)
        return answer, interview

    @staticmethod
    def cancel_interview(interview_id: uuid.UUID, user: User) -> Interview:
        interview = InterviewService._get_interview(interview_id, user, require_active=True)
        interview.status = InterviewStatus.CANCELLED
        interview.save(update_fields=["status", "updated_at"])

        from apps.analytics.services import AnalyticsService
        AnalyticsService.generate_result(interview)

        logger.info("Interview %s cancelled after %d questions", interview_id, interview.completed_questions)
        return interview

    @staticmethod
    def _process_video(video_file) -> tuple[str, dict]:
        tmp_video_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp_video_path = tmp.name
                for chunk in video_file.chunks():
                    tmp.write(chunk)

            return SpeechToTextService.transcribe(tmp_video_path)
        finally:
            if tmp_video_path and os.path.exists(tmp_video_path):
                try:
                    os.remove(tmp_video_path)
                except OSError:
                    pass

    @staticmethod
    def _get_interview(interview_id: uuid.UUID, user: User, require_active: bool) -> Interview:
        try:
            interview = Interview.objects.get(id=interview_id, user=user)
        except Interview.DoesNotExist:
            raise ValueError("Interview not found.")

        if require_active:
            if interview.status != InterviewStatus.ACTIVE:
                raise ValueError(
                    f"This interview has already ended (status: {interview.status}). "
                    "No further answers can be submitted."
                )
        else:
            if interview.status not in READABLE_STATUSES:
                raise ValueError(f"Interview is not accessible (status: {interview.status}).")

        return interview

    @staticmethod
    def get_history(user: User) -> list[Interview]:
        return (
            Interview.objects
            .filter(user=user)
            .exclude(status=InterviewStatus.PENDING)
            .order_by("-created_at")
        )
