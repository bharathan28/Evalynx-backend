"""
Speech-to-Text Service — Powered by Google Gemini.

Gemini 1.5 Flash/Pro natively understands audio, so we send the extracted
audio file directly — no separate Whisper dependency needed.

Pipeline:
  1. Extract audio from video using ffmpeg (16kHz mono WAV — minimal size)
  2. Upload audio to Gemini Files API (temp upload, auto-deleted by Google)
  3. Ask Gemini to transcribe
  4. Delete local temp files immediately

Gemini Files API auto-deletes uploaded files after 48 hours, but we also
explicitly delete after transcription for privacy compliance.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


def _configure():
    genai.configure(api_key=settings.GEMINI_API_KEY)

_configure()

_TRANSCRIPTION_PROMPT = (
    "Transcribe the speech in this audio file exactly as spoken. "
    "Output only the transcription text — no labels, no timestamps, "
    "no commentary, no formatting. If the audio is silent or inaudible, "
    "output an empty string."
)


class SpeechToTextService:

    @classmethod
    def transcribe(cls, video_path: str) -> tuple[str, dict]:
        """
        Extract audio from video, transcribe via Gemini, return
        (transcript_text, audio_metadata). All temp files are deleted here.
        The caller is responsible for deleting the original video file.
        """
        audio_path: str | None = None
        gemini_file = None

        try:
            audio_path, duration_seconds = cls._extract_audio(video_path)
            gemini_file = cls._upload_to_gemini(audio_path)
            transcript = cls._transcribe_with_gemini(gemini_file)

            metadata = {
                "duration_seconds": duration_seconds,
                "word_count": len(transcript.split()),
            }
            return transcript, metadata

        except Exception as exc:
            logger.exception("Transcription error for %s: %s", video_path, exc)
            return "", {}

        finally:
            # Delete local audio temp file
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.debug("Temp audio deleted: %s", audio_path)
            # Delete uploaded Gemini file
            if gemini_file:
                try:
                    genai.delete_file(gemini_file.name)
                    logger.debug("Gemini file deleted: %s", gemini_file.name)
                except Exception:
                    pass  # Non-fatal — Gemini auto-deletes after 48h anyway

    @classmethod
    def _extract_audio(cls, video_path: str) -> tuple[str, float]:
        """
        Use ffmpeg to extract audio as 16kHz mono WAV.
        16kHz mono is optimal for speech recognition and minimises upload size.
        Returns (audio_path, duration_seconds).
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="/tmp") as tmp:
            audio_path = tmp.name

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",                    # Drop video stream
            "-acodec", "pcm_s16le",  # Raw PCM
            "-ac", "1",              # Mono
            "-ar", "16000",          # 16 kHz
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg audio extraction failed: {result.stderr.decode()[:500]}"
            )

        return audio_path, cls._get_duration(audio_path)

    @staticmethod
    def _upload_to_gemini(audio_path: str):
        """
        Upload audio to the Gemini Files API.
        Waits until the file is in ACTIVE state before returning.
        """
        uploaded = genai.upload_file(path=audio_path, mime_type="audio/wav")

        # Poll until ACTIVE (usually instant for short files)
        max_wait = 30
        waited = 0
        while uploaded.state.name == "PROCESSING" and waited < max_wait:
            time.sleep(1)
            waited += 1
            uploaded = genai.get_file(uploaded.name)

        if uploaded.state.name != "ACTIVE":
            raise RuntimeError(
                f"Gemini file upload failed — state: {uploaded.state.name}"
            )

        return uploaded

    @staticmethod
    def _transcribe_with_gemini(gemini_file) -> str:
        """Send the uploaded audio file to Gemini for transcription."""
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_AUDIO_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=4096,
            ),
        )
        response = model.generate_content([_TRANSCRIPTION_PROMPT, gemini_file])
        return response.text.strip() if response.text else ""

    @staticmethod
    def _get_duration(audio_path: str) -> float:
        """Get audio duration in seconds via ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip()) if result.stdout.strip() else 0.0
        except Exception:
            return 0.0
