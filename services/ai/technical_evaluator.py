"""
Technical Evaluator Service — Powered by Google Gemini.

One Gemini API call per submitted answer.
Evaluates technical accuracy, completeness, and provides structured feedback.
"""

from __future__ import annotations

import json
import logging
import re
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
        Returns a structured result dict. Always returns a safe fallback on failure.
        """
        if not transcript.strip():
            return cls._no_answer_result()

        try:
            prompt = _PROMPT_TEMPLATE.format(
                question=question[:2000],
                transcript=transcript[:4000],
            )
        except Exception as exc:
            logger.error("Evaluation prompt formatting failed: %s", exc)
            return cls._error_result()

        try:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
            )
            response = model.generate_content(prompt)

            raw = response.text.strip()

            # Strip markdown fences if Gemini wraps the response
            raw = raw.replace("```json", "").replace("```", "").strip()

            # Extract first JSON object found in the response
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                logger.error("Gemini evaluation returned no JSON object.")
                return cls._error_result()

            result = json.loads(match.group(0))

            return {
                "technical_score": max(0.0, min(10.0, float(result.get("technical_score", 0)))),
                "completeness_score": max(0.0, min(10.0, float(result.get("completeness_score", 0)))),
                "missing_concepts": result.get("missing_concepts", []),
                "mistakes": result.get("mistakes", []),
                "feedback": result.get("feedback", ""),
                "better_answer": result.get("better_answer", ""),
            }

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
            "mistakes": ["No answer provided."],
            "feedback": "No answer was detected for this question.",
            "better_answer": "",
        }

    @staticmethod
    def _error_result() -> dict:
        return {
            "technical_score": 0.0,
            "completeness_score": 0.0,
            "missing_concepts": [],
            "mistakes": [],
            "feedback": "Evaluation unavailable due to a processing error.",
            "better_answer": "",
        }
