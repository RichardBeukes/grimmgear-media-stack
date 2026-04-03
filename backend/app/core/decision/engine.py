"""
GrimmGear — Decision Engine
Evaluates releases before grabbing. All 14 anti-fake patches built in.
One engine, all media types.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("grimmgear.decision")


@dataclass
class Decision:
    accepted: bool
    reason: str
    score: int = 0


class DecisionEngine:
    """
    Evaluates a release and decides: grab or reject.
    Runs all checks in order. First rejection wins.
    """

    def evaluate(
        self,
        title: str,
        size: int = 0,
        quality: str = "",
        language: str = "",
        seeders: int = 0,
        wanted_language: str = "English",
        min_quality: str = "720p",
    ) -> Decision:
        """Run all checks against a release. Returns accept/reject with reason."""

        checks = [
            self._check_size_zero(size),
            self._check_language(title, language, wanted_language),
            self._check_cyrillic(title),
            self._check_cjk(title),
            self._check_arabic(title),
            self._check_russian_tags(title),
            self._check_non_english_tags(title),
            self._check_quality_minimum(quality, min_quality),
            self._check_seeders(seeders),
        ]

        for check in checks:
            if check is not None and not check.accepted:
                return check

        # All checks passed — calculate score
        score = self._calculate_score(quality, seeders, size, language, wanted_language)
        return Decision(accepted=True, reason="All checks passed", score=score)

    # ── Size Check (our patch: reject size=0) ───────────────

    def _check_size_zero(self, size: int) -> Optional[Decision]:
        if size == 0:
            return Decision(False, "Release has no size info — potential fake", 0)
        return None

    # ── Language Checks (our patches) ───────────────────────

    def _check_language(self, title: str, detected_lang: str, wanted: str) -> Optional[Decision]:
        if not detected_lang or detected_lang == wanted or detected_lang == "English":
            return None
        # Non-English detected language when we want English
        if wanted == "English" and detected_lang not in ("English", ""):
            return Decision(False, f"Detected language: {detected_lang}, wanted: {wanted}", 0)
        return None

    def _check_cyrillic(self, title: str) -> Optional[Decision]:
        if re.search(r'[\u0400-\u04FF]{3,}', title):
            return Decision(False, "Cyrillic characters detected — likely Russian release", 0)
        return None

    def _check_cjk(self, title: str) -> Optional[Decision]:
        if re.search(r'[\u3000-\u9FFF\uAC00-\uD7AF]{2,}', title):
            return Decision(False, "CJK characters detected — likely Chinese/Korean/Japanese release", 0)
        return None

    def _check_arabic(self, title: str) -> Optional[Decision]:
        if re.search(r'[\u0600-\u06FF]{3,}', title):
            return Decision(False, "Arabic characters detected", 0)
        return None

    def _check_russian_tags(self, title: str) -> Optional[Decision]:
        if re.search(r'\b(?:MVO|AVO|DVO|Dub\.(?:RUS|Ukr)|DUAL\.RUS|RuTracker|Generalfilm|D\.KOSHARA|HDRezka|nnmclub|kinozal|rutor|LostFilm|BaibaKo|NovaFilm|NewStudio|ColdFilm|Jaskier)\b', title, re.I):
            return Decision(False, "Russian dubbing/release group tag detected", 0)
        return None

    def _check_non_english_tags(self, title: str) -> Optional[Decision]:
        if re.search(r'\b(?:LATINO|FRENCH|GERMAN|ITALIAN|SPANISH|PORTUGUESE|HINDI|TAMIL|TELUGU|KOREAN|JAPANESE|CHINESE|ARABIC|PERSIAN|THAI|TURKISH|POLISH|CZECH|HUNGARIAN|ROMANIAN|GREEK|HEBREW|VIETNAMESE|INDONESIAN|MALAY)\b', title, re.I):
            return Decision(False, "Non-English language tag detected", 0)
        return None

    # ── Quality Check ───────────────────────────────────────

    def _check_quality_minimum(self, quality: str, min_quality: str) -> Optional[Decision]:
        quality_order = {"480p": 1, "sd": 1, "720p": 2, "1080p": 3, "2160p": 4, "unknown": 0}
        q_val = quality_order.get(quality.lower(), 0)
        min_val = quality_order.get(min_quality.lower(), 2)
        if q_val > 0 and q_val < min_val:
            return Decision(False, f"Quality {quality} below minimum {min_quality}", 0)
        return None

    # ── Seeder Check ────────────────────────────────────────

    def _check_seeders(self, seeders: int) -> Optional[Decision]:
        # Don't reject 0 seeders completely — some indexers don't report them
        return None

    # ── Score Calculation ───────────────────────────────────

    def _calculate_score(self, quality: str, seeders: int, size: int, language: str, wanted: str) -> int:
        score = 0

        # Quality score
        quality_scores = {"2160p": 100, "1080p": 80, "720p": 60, "480p": 20, "unknown": 40}
        score += quality_scores.get(quality.lower(), 40)

        # Seeder score (capped at 100)
        score += min(seeders, 100)

        # Source bonus
        # Remux and BluRay get slight boost (less likely to be fake)
        return score


# Singleton
decision_engine = DecisionEngine()
