"""
Technical Evaluator Service — Powered by Google Gemini.

One Gemini API call per submitted answer.
Evaluates technical accuracy, completeness, and provides structured feedback.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "evaluation_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")


def _configure():
    genai.configure(api_key=settings.GEMINI_API_KEY)

_configure()


class TechnicalEvaluatorService:

    @classmethod
    def evaluate(cls, question: str, transcript: str) -> dict:
        """
        Evaluate the candidate's answer using Gemini.
        Returns a dict with scores, feedback, and a model answer.
        Always returns a safe default dict on failure.
        """
        if not transcript.strip():
            return cls._no_answer_result()

        prompt = _PROMPT_TEMPLATE.format(
            question=question[:2000],
            transcript=transcript[:4000],
        )

        try:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.0,        # Consistent, reproducible scoring
                    max_output_tokens=1200,
                ),
            )

            response = model.generate_content(prompt)
            result = json.loads(response.text)

            # Clamp scores to [0, 10]
            for score_key in ("technical_score", "completeness_score"):
                if score_key in result and result[score_key] is not None:
                    result[score_key] = max(0.0, min(10.0, float(result[score_key])))

            return result

        except json.JSONDecodeError as exc:
            logger.error("Evaluator JSON decode error: %s", exc)
            return cls._error_result()
        except Exception as exc:
            logger.exception("Evaluator Gemini error: %s", exc)
            return cls._error_result()

    @staticmethod
    def _no_answer_result() -> dict:
        return {
            "technical_score": 0.0,
            "completeness_score": 0.0,
            "missing_concepts": [],
            "mistakes": ["No answer was provided."],
            "feedback": "No answer was detected for this question.",
            "better_answer": "",
        }

    @staticmethod
    def _error_result() -> dict:
        return {
            "technical_score": None,
            "completeness_score": None,
            "missing_concepts": [],
            "mistakes": [],
            "feedback": "Evaluation unavailable due to a processing error.",
            "better_answer": "",
        }
