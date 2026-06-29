"""
Grammar Checker Service.

Uses LanguageTool (local Java server via language-tool-python).
Zero API cost. Pure local processing.

On first use, language-tool-python downloads the LanguageTool JAR (~200 MB).
Subsequent calls reuse the cached JAR.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Lazily initialise LanguageTool to avoid slowing down startup
_tool = None


def _get_tool():
    global _tool
    if _tool is None:
        try:
            import language_tool_python
            _tool = language_tool_python.LanguageTool("en-US")
        except Exception as exc:
            logger.error("LanguageTool initialisation failed: %s", exc)
    return _tool


class GrammarCheckerService:

    @staticmethod
    def check(text: str) -> dict:
        """
        Check transcript for grammar errors.

        Returns:
          grammar_score     — 0–10 (10 = perfect)
          mistake_count     — total grammar issues found
          suggestions       — list of correction dicts
        """
        if not text.strip():
            return GrammarCheckerService._empty_result()

        tool = _get_tool()
        if tool is None:
            # LanguageTool unavailable — return neutral score rather than crashing
            logger.warning("LanguageTool unavailable. Returning neutral grammar score.")
            return {"grammar_score": 7.0, "mistake_count": 0, "suggestions": []}

        try:
            matches = tool.check(text)

            suggestions = [
                {
                    "message": m.message,
                    "context": m.context,
                    "replacements": m.replacements[:3],  # Top 3 suggested fixes
                    "rule_id": m.ruleId,
                }
                for m in matches[:20]  # Cap at 20 for response size
            ]

            mistake_count = len(matches)
            grammar_score = GrammarCheckerService._compute_score(text, mistake_count)

            return {
                "grammar_score": grammar_score,
                "mistake_count": mistake_count,
                "suggestions": suggestions,
            }

        except Exception as exc:
            logger.error("Grammar check error: %s", exc)
            return GrammarCheckerService._empty_result()

    @staticmethod
    def _compute_score(text: str, mistake_count: int) -> float:
        """
        Score grammar on a 0–10 scale.
        Penalty is proportional to mistake density (mistakes per 100 words).
        """
        word_count = max(len(text.split()), 1)
        mistake_density = (mistake_count / word_count) * 100

        # Each mistake per 100 words deducts ~1.5 points
        score = max(0.0, 10.0 - mistake_density * 1.5)
        return round(score, 2)

    @staticmethod
    def _empty_result() -> dict:
        return {"grammar_score": 0.0, "mistake_count": 0, "suggestions": []}
