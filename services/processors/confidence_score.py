"""
Confidence Score Engine.

Algorithm-based. Zero external dependencies. Zero API cost.

Computes two scores from transcript + audio metadata:
  confidence_score    — how confident the speaker sounds (delivery)
  communication_score — how clearly ideas are structured and expressed

Both scores are on a 0–10 scale.

Signals used (derived from transcript text and audio metadata):
  - Speaking rate (words per minute)
  - Filler word density
  - Answer length (word count)
  - Sentence variety (average sentence length)
  - Audio duration vs. transcript length correlation
"""

from __future__ import annotations

import re


class ConfidenceScoreService:

    # Tuneable constants
    IDEAL_WPM_MIN = 110
    IDEAL_WPM_MAX = 160
    FILLER_PENALTY_PER_WORD = 0.25
    MIN_WORDS_FOR_FULL_SCORE = 40
    MAX_CONFIDENCE_SCORE = 10.0

    @classmethod
    def compute(cls, transcript: str, audio_metadata: dict, filler_count: int) -> dict:
        """
        Compute confidence and communication scores.

        Args:
          transcript      — full transcribed text
          audio_metadata  — { duration_seconds, word_count }
          filler_count    — total filler words detected

        Returns:
          { confidence_score, communication_score }
        """
        if not transcript.strip():
            return {"confidence_score": 0.0, "communication_score": 0.0}

        words = transcript.split()
        word_count = len(words)
        duration = float(audio_metadata.get("duration_seconds", 0))

        confidence = cls._compute_confidence(word_count, duration, filler_count)
        communication = cls._compute_communication(transcript, word_count, filler_count)

        return {
            "confidence_score": confidence,
            "communication_score": communication,
        }

    @classmethod
    def _compute_confidence(cls, word_count: int, duration: float, filler_count: int) -> float:
        """
        Confidence approximation:
          - Start at 10
          - Penalise for too slow / too fast speaking rate
          - Penalise for filler words
          - Penalise for very short answers (signals reluctance or lack of knowledge)
        """
        score = cls.MAX_CONFIDENCE_SCORE

        # ── Speaking rate penalty ─────────────────────────────────────────────
        if duration > 0:
            wpm = (word_count / duration) * 60
            if wpm < cls.IDEAL_WPM_MIN:
                score -= (cls.IDEAL_WPM_MIN - wpm) / 20     # Too slow
            elif wpm > cls.IDEAL_WPM_MAX:
                score -= (wpm - cls.IDEAL_WPM_MAX) / 30     # Too fast

        # ── Filler word penalty ───────────────────────────────────────────────
        score -= filler_count * cls.FILLER_PENALTY_PER_WORD

        # ── Answer length penalty ─────────────────────────────────────────────
        if word_count < cls.MIN_WORDS_FOR_FULL_SCORE:
            score -= (cls.MIN_WORDS_FOR_FULL_SCORE - word_count) * 0.05

        return round(max(0.0, min(cls.MAX_CONFIDENCE_SCORE, score)), 2)

    @classmethod
    def _compute_communication(cls, transcript: str, word_count: int, filler_count: int) -> float:
        """
        Communication clarity approximation:
          - Start at 10
          - Penalise for filler density
          - Penalise for very short or very long average sentence length
          - Reward appropriate answer length
        """
        score = cls.MAX_CONFIDENCE_SCORE

        # ── Filler density penalty ────────────────────────────────────────────
        filler_density = filler_count / max(word_count, 1)
        score -= filler_density * 20  # 5% filler density → -1 point

        # ── Sentence structure analysis ───────────────────────────────────────
        sentences = re.split(r"[.!?]+", transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            # Penalise extremes: very short (fragmented) or very long (rambling)
            if avg_sentence_length < 8:
                score -= (8 - avg_sentence_length) * 0.3
            elif avg_sentence_length > 35:
                score -= (avg_sentence_length - 35) * 0.15

        # ── Answer length bonus/penalty ───────────────────────────────────────
        if word_count < 30:
            score -= 2.0   # Very brief — likely incomplete
        elif word_count > 400:
            score -= 1.0   # Rambling

        return round(max(0.0, min(cls.MAX_CONFIDENCE_SCORE, score)), 2)
