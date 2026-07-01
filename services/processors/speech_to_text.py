"""
Speech to Text Service — Local Whisper (no API cost per call).

Flow:
  video (.webm) -> ffmpeg extract audio (.wav) -> whisper transcribe -> text

The Whisper model is loaded LAZILY on first use (not at import time).
This prevents the entire Django process from crashing on startup if the
model download fails, torch isn't available, or there's no internet on
first boot. Subsequent calls reuse the cached model instance.

ffmpeg / ffprobe paths are read from Django settings (FFMPEG_PATH /
FFPROBE_PATH), which default to "ffmpeg" / "ffprobe" on PATH but can be
overridden in .env — this matters most on Windows where ffmpeg often
isn't globally registered on PATH.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from django.conf import settings

logger = logging.getLogger(__name__)

# Lazily-loaded global model — populated on first transcribe() call
_WHISPER_MODEL = None


def _get_whisper_model():
    """Load the Whisper model once, on first use, and cache it."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        import whisper  # Imported here so a missing/broken install doesn't crash startup
        logger.info("Loading Whisper model (base) — first use only, may take a moment…")
        _WHISPER_MODEL = whisper.load_model("base")
        logger.info("Whisper model loaded successfully.")
    return _WHISPER_MODEL


class SpeechToTextService:

    @classmethod
    def transcribe(cls, video_path: str) -> tuple[str, dict]:
        """
        Extract audio from video and transcribe using local Whisper.
        Returns (transcript, metadata). Raises ValueError with a clear
        message on failure so the caller can surface it to the user.
        """
        audio_path: str | None = None

        try:
            audio_path, duration = cls._extract_audio(video_path)

            model = _get_whisper_model()
            result = model.transcribe(audio_path, language="en", fp16=False)
            transcript = (result.get("text") or "").strip()

            metadata = {
                "duration_seconds": duration,
                "word_count": len(transcript.split()),
            }
            return transcript, metadata

        except FileNotFoundError as exc:
            # ffmpeg/ffprobe binary not found on the system
            logger.exception("ffmpeg/ffprobe not found: %s", exc)
            raise ValueError(
                "Audio processing tool (ffmpeg) was not found on this server. "
                "Install ffmpeg and ensure it's on PATH, or set FFMPEG_PATH / "
                "FFPROBE_PATH in your .env file to the full executable path."
            ) from exc

        except Exception as exc:
            logger.exception("Transcription error: %s", exc)
            raise ValueError(f"Transcription failed: {exc}") from exc

        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except OSError:
                    pass

    @classmethod
    def _extract_audio(cls, video_path: str) -> tuple[str, float]:
        """Extract 16kHz mono WAV audio from the video using ffmpeg."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name

        ffmpeg_bin = getattr(settings, "FFMPEG_PATH", "ffmpeg")

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "16000",
            audio_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
        except FileNotFoundError:
            # Re-raise with the binary name so the caller's message is accurate
            raise FileNotFoundError(f"'{ffmpeg_bin}' executable not found")

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="ignore")[:500]
            raise RuntimeError(f"ffmpeg failed: {stderr}")

        duration = cls._get_duration(audio_path)
        return audio_path, duration

    @staticmethod
    def _get_duration(audio_path: str) -> float:
        """Get audio duration in seconds via ffprobe. Returns 0.0 on any failure."""
        ffprobe_bin = getattr(settings, "FFPROBE_PATH", "ffprobe")
        try:
            cmd = [
                ffprobe_bin,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip()) if result.stdout.strip() else 0.0
        except Exception:
            return 0.0
