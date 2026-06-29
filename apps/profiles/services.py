"""
Profile service layer.

Responsibilities:
  1. Extract raw text from the uploaded PDF (PyMuPDF)
  2. Delete the temp file immediately after extraction
  3. Dispatch raw text to the AI resume parser
  4. Upsert the extracted data into the user's Profile record

No PDF bytes are ever written to the database.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone

import fitz  # PyMuPDF

from apps.authentication.models import User
from services.ai.resume_parser import ResumeParserService

from .models import Profile

logger = logging.getLogger(__name__)


class ProfileService:
    @staticmethod
    def process_resume(user: User, file) -> Profile:
        """
        End-to-end resume pipeline:
          upload → extract text → AI parse → store → discard file
        """
        raw_text = ProfileService._extract_pdf_text(file)

        if not raw_text.strip():
            raise ValueError(
                "Could not extract readable text from the PDF. "
                "Ensure the resume is not a scanned image without OCR."
            )

        structured_data = ResumeParserService.parse(raw_text)

        profile = ProfileService._upsert_profile(user, raw_text, structured_data)

        logger.info("Resume processed successfully for user %s", user.id)
        return profile

    @staticmethod
    def _extract_pdf_text(file) -> str:
        """
        Write the uploaded file to a temp path, extract text via PyMuPDF,
        then delete the temp file immediately — even if an error occurs.
        """
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, dir="/tmp"
            ) as tmp:
                tmp_path = tmp.name
                for chunk in file.chunks():
                    tmp.write(chunk)

            doc = fitz.open(tmp_path)
            pages_text = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(pages_text)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug("Temp PDF deleted: %s", tmp_path)

    @staticmethod
    def _upsert_profile(user: User, raw_text: str, data: dict) -> Profile:
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.full_name = data.get("full_name", user.name)
        profile.education = data.get("education", [])
        profile.skills = data.get("skills", [])
        profile.experience = data.get("experience", [])
        profile.projects = data.get("projects", [])
        profile.certifications = data.get("certifications", [])
        profile.raw_resume_text = raw_text
        profile.resume_parsed_at = datetime.now(tz=timezone.utc)
        profile.save()
        return profile

    @staticmethod
    def get_or_create_profile(user: User) -> Profile:
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile
