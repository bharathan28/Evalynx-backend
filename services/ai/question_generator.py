"""
Question Generator Service — Powered by Google Gemini.

Single Gemini API call per interview start.
Generates technically relevant, candidate-tailored interview questions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "question_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


def _configure():
    genai.configure(api_key=settings.GEMINI_API_KEY)

_configure()


class QuestionGeneratorService:

    @classmethod
    def generate(cls, profile: dict, job_description: str, count: int) -> list[str]:
        """
        Generate `count` interview questions tailored to the candidate + role.
        Returns a list of question strings. Falls back to generic questions on error.
        """
        prompt = _PROMPT_TEMPLATE.format(
            count=count,
            job_description=job_description[:3000],
            skills=", ".join(profile.get("skills", [])) or "Not provided",
            experience=cls._summarise_experience(profile.get("experience", [])),
            projects=cls._summarise_projects(profile.get("projects", [])),
            certifications=", ".join(profile.get("certifications", [])) or "None",
        )

        try:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.7,        # Slight creativity for variety
                    max_output_tokens=1500,
                ),
            )

            response = model.generate_content(prompt)
            parsed = json.loads(response.text)

            # Response may be a list directly or wrapped in an object key
            if isinstance(parsed, list):
                questions = parsed
            else:
                questions = next(
                    (v for v in parsed.values() if isinstance(v, list)), []
                )

            questions = [str(q) for q in questions[:count]]

            # Pad with fallbacks if Gemini returned fewer than requested
            if len(questions) < count:
                questions += cls._fallback_questions(count - len(questions))

            return questions

        except Exception as exc:
            logger.exception("Question generator Gemini error: %s", exc)
            return cls._fallback_questions(count)

    @staticmethod
    def _summarise_experience(experience: list[dict]) -> str:
        if not experience:
            return "Not provided"
        parts = [
            f"{e.get('role', '')} at {e.get('company', '')} "
            f"({e.get('start_date', '')}–{e.get('end_date', '')})"
            for e in experience[:4]
        ]
        return "; ".join(parts)

    @staticmethod
    def _summarise_projects(projects: list[dict]) -> str:
        if not projects:
            return "Not provided"
        parts = [
            f"{p.get('name', '')} ({', '.join(p.get('technologies', [])[:3])})"
            for p in projects[:3]
        ]
        return "; ".join(parts)

    @staticmethod
    def _fallback_questions(count: int) -> list[str]:
        generic = [
            "Tell me about a challenging technical problem you solved and how you approached it.",
            "How do you ensure the quality and maintainability of your code?",
            "Describe a situation where you had to learn a new technology quickly.",
            "How do you approach system design for a scalable web application?",
            "Explain how you debug a production issue under time pressure.",
            "What software engineering principles guide your daily work?",
            "Describe your experience working in an agile team environment.",
            "How do you handle disagreements with teammates on technical decisions?",
            "Walk me through the architecture of the most complex system you've built.",
            "How do you stay current with new developments in your technical domain?",
        ]
        return generic[:count]
