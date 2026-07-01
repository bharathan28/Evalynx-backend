"""
Resume Parser Service — Powered by Google Gemini.

Single Gemini API call that converts raw resume text into structured JSON.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "resume_prompt.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


class ResumeParserService:

    @classmethod
    def parse(cls, raw_text: str) -> dict:
        """Parse raw resume text into a structured profile dict using Gemini."""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)

            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=8192,
                ),
            )

            prompt = f"{_SYSTEM_PROMPT}\n\nParse this resume:\n\n{raw_text[:6000]}"
            response = model.generate_content(prompt)
            return json.loads(response.text)

        except json.JSONDecodeError as exc:
            logger.error("Resume parser — Gemini returned invalid JSON: %s", exc)
            return cls._empty_profile()

        except Exception as exc:
            logger.exception("Resume parser Gemini error: %s", exc)
            return cls._empty_profile()

    @staticmethod
    def _empty_profile() -> dict:
        return {
            "full_name": "",
            "education": [],
            "skills": [],
            "experience": [],
            "projects": [],
            "certifications": [],
        }
