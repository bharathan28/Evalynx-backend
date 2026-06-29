
from __future__ import annotations

import json
import logging
from pathlib import Path

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "resume_prompt.txt"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Gemini client is configured once at module level
def _configure():
    genai.configure(api_key=settings.GEMINI_API_KEY)

_configure()


class ResumeParserService:

    @classmethod
    def parse(cls, raw_text: str) -> dict:
        """
        Parse raw resume text into a structured profile dict using Gemini.
        Falls back to an empty profile on any error to avoid blocking the flow.
        """
        try:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",  # Force JSON output
                    temperature=0.0,                        # Deterministic extraction
                    max_output_tokens=2000,
                ),
            )

            prompt = f"{_SYSTEM_PROMPT}\n\nParse this resume:\n\n{raw_text[:12000]}"
            response = model.generate_content(prompt)
            return json.loads(response.text)

        except json.JSONDecodeError as exc:
            logger.error("Resume parser JSON decode error: %s", exc)
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
