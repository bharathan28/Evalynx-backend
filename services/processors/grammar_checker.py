"""
Grammar Checker Service.

Uses LanguageTool (local). Zero API cost.

The LanguageTool server/JAR is loaded LAZILY on first use rather than at
import time. This avoids crashing Django on startup if Java isn't
installed or the JAR hasn't been downloaded yet — instead, grammar
checks degrade gracefully to a neutral score until LanguageTool is
available.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_TOOL = None
_TOOL_INIT_FAILED = False


def _get_tool():
    global _TOOL, _TOOL_INIT_FAILED
    if _TOOL is not None or _TOOL_INIT_FAILED:
        return _TOOL
    try:
        import language_tool_python
        logger.info("Initialising LanguageTool (first use only)…")
        _TOOL = language_tool_python.LanguageTool("en-US")
        logger.info("LanguageTool ready.")
    except Exception as exc:
        _TOOL_INIT_FAILED = True
        logger.error("LanguageTool initialisation failed — grammar checks will be skipped: %s", exc)
    return _TOOL


class GrammarCheckerService:

    @staticmethod
    def check(text: str) -> dict:
        """
        Check transcript grammar.

        Returns:
          grammar_score  -> 0–10
          mistake_count  -> total mistakes
          suggestions    -> correction suggestions
        """
        if not text.strip():
            return {"grammar_score": 0.0, "mistake_count": 0, "suggestions": []}

        tool = _get_tool()
        if tool is None:
            # LanguageTool unavailable — neutral score so the pipeline keeps moving
            return {"grammar_score": 7.0, "mistake_count": 0, "suggestions": []}

        try:
            matches = tool.check(text)

            suggestions = [
                {
                    "message": m.message,
                    "context": m.context,
                    "replacements": m.replacements[:3],
                    "rule_id": m.ruleId,
                }
                for m in matches[:20]
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
            return {"grammar_score": 7.0, "mistake_count": 0, "suggestions": []}

    @staticmethod
    def _compute_score(text: str, mistake_count: int) -> float:
        word_count = max(len(text.split()), 1)
        mistake_density = (mistake_count / word_count) * 100
        score = max(0.0, 10.0 - mistake_density * 1.5)
        return round(score, 2)
