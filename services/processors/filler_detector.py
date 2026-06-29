"""
Filler Word Detector.

Pure Python. Zero external dependencies. Zero API cost.

Detects common spoken filler words in transcribed text.
Uses whole-word matching to avoid false positives
(e.g. "basically" in "basically" vs "basic").
"""

from __future__ import annotations

import re

# Ordered by how disruptive they typically are in interviews
FILLER_WORDS: list[str] = [
    "umm", "ummm", "um",
    "uhh", "uh", "uhhhh",
    "like",
    "you know",
    "basically",
    "literally",
    "actually",
    "sort of",
    "kind of",
    "right",
    "so",
    "anyway",
    "I mean",
]

# Normalise multi-word fillers for phrase detection
_PHRASE_FILLERS = {f for f in FILLER_WORDS if " " in f}
_WORD_FILLERS = {f for f in FILLER_WORDS if " " not in f}


class FillerDetectorService:

    @staticmethod
    def detect(text: str) -> dict:
        """
        Scan transcript for filler words.

        Returns:
          total_count  — sum of all filler occurrences
          details      — { filler_word: count } (only words with count > 0)
        """
        if not text.strip():
            return {"total_count": 0, "details": {}}

        normalised = text.lower()
        details: dict[str, int] = {}

        # Phrase detection first (multi-word fillers)
        for phrase in _PHRASE_FILLERS:
            count = len(re.findall(r"\b" + re.escape(phrase) + r"\b", normalised))
            if count:
                details[phrase] = count

        # Single-word detection
        words = re.findall(r"\b\w+\b", normalised)
        for word in words:
            if word in _WORD_FILLERS:
                details[word] = details.get(word, 0) + 1

        # Remove zero-count entries
        details = {k: v for k, v in details.items() if v > 0}
        total_count = sum(details.values())

        return {"total_count": total_count, "details": details}
