from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
import importlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

Replacement = str | Callable[[re.Match[str]], str]


def _load_presidio_engines() -> tuple[type[Any] | None, type[Any] | None]:
    try:
        analyzer_module = importlib.import_module("presidio_analyzer")
        anonymizer_module = importlib.import_module("presidio_anonymizer")
    except Exception as exc:  # noqa: BLE001
        logger.info("Presidio is unavailable. Regex masking will be used instead: %s", exc)
        return None, None

    return (
        getattr(analyzer_module, "AnalyzerEngine", None),
        getattr(anonymizer_module, "AnonymizerEngine", None),
    )


@dataclass(slots=True)
class MaskingResult:
    text: str
    method: str
    replacements: int
    applied_presidio: bool
    applied_regex: bool
    pattern_hits: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class MaskingPipeline:
    """Mask school-record PII with regex by default and Presidio when available."""

    REGEX_RULES: tuple[tuple[str, re.Pattern[str], Replacement], ...] = (
        (
            "resident_registration_number",
            re.compile(r"\b\d{6}\s*[-]?\s*[1-4]\d{6}\b"),
            "[RRN_MASKED]",
        ),
        (
            "phone_number",
            re.compile(r"\b(?:01[016789]|0[2-9]\d?)\s*[-]?\s*\d{3,4}\s*[-]?\s*\d{4}\b"),
            "[PHONE_MASKED]",
        ),
        (
            "email_address",
            re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
            "[EMAIL_MASKED]",
        ),
        (
            "birth_date",
            re.compile(r"\b(?:19|20)\d{2}[./-](?:0?[1-9]|1[0-2])[./-](?:0?[1-9]|[12]\d|3[01])\b"),
            "[BIRTHDATE_MASKED]",
        ),
        (
            "student_number_label",
            re.compile(
                r"(?P<label>(?:\uD559\uBC88|\uC218\uD5D8\uBC88\uD638|student\s*id)\s*[:：]?\s*)(?P<value>[A-Za-z0-9-]{4,20})",
                re.IGNORECASE,
            ),
            lambda match: f"{match.group('label')}[ID_MASKED]",
        ),
        (
            "student_name_label",
            re.compile(
                r"(?P<label>(?:\uC131\uBA85|\uC774\uB984|student\s*name)\s*[:：]?\s*)(?P<value>[\uAC00-\uD7A3A-Za-z]{2,20})",
                re.IGNORECASE,
            ),
            lambda match: f"{match.group('label')}[NAME_MASKED]",
        ),
        (
            "guardian_name_label",
            re.compile(
                r"(?P<label>(?:\uBCF4\uD638\uC790\s*\uC131\uBA85|\uBD80\uBAA8\s*\uC131\uBA85|guardian\s*name)\s*[:：]?\s*)(?P<value>[\uAC00-\uD7A3A-Za-z]{2,20})",
                re.IGNORECASE,
            ),
            lambda match: f"{match.group('label')}[GUARDIAN_MASKED]",
        ),
        (
            "school_name",
            re.compile(
                r"(?<!\[)[\uAC00-\uD7A3A-Za-z0-9]{2,30}(?:\uCD08\uB4F1\uD559\uAD50|\uC911\uD559\uAD50|\uACE0\uB4F1\uD559\uAD50)\b"
            ),
            "[SCHOOL_MASKED]",
        ),
        (
            "photo_marker",
            re.compile(r"(?:\uC99D\uBA85\uC0AC\uC9C4|\uD559\uC0DD\uC0AC\uC9C4|\uC0AC\uC9C4)"),
            "[PHOTO_REMOVED]",
        ),
    )

    def __init__(self) -> None:
        analyzer_cls, anonymizer_cls = _load_presidio_engines()
        self.analyzer = None
        self.anonymizer = None

        if analyzer_cls is None or anonymizer_cls is None:
            return

        try:
            self.analyzer = analyzer_cls()
            self.anonymizer = anonymizer_cls()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to initialize Presidio. Regex masking only will be used: %s", exc)

    def apply_masking(self, text: str) -> str:
        return self.mask_text(text).text

    def mask_text(self, text: str) -> MaskingResult:
        if not text:
            return MaskingResult(
                text=text,
                method="none",
                replacements=0,
                applied_presidio=False,
                applied_regex=False,
            )

        working_text = text
        warnings: list[str] = []
        replacements = 0
        applied_presidio = False

        if self.analyzer is not None and self.anonymizer is not None:
            try:
                results = self.analyzer.analyze(
                    text=working_text,
                    language="en",
                    entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "LOCATION", "DATE_TIME"],
                )
                if results:
                    applied_presidio = True
                    replacements += len(results)
                    anonymized = self.anonymizer.anonymize(text=working_text, analyzer_results=results)
                    working_text = anonymized.text
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Presidio masking failed: {exc}")
                logger.warning("Presidio masking failed. Falling back to regex: %s", exc)

        working_text, regex_hits, regex_replacements = self._apply_regex_fallback(working_text)
        replacements += regex_replacements

        if applied_presidio and regex_replacements:
            method = "presidio+regex"
        elif applied_presidio:
            method = "presidio"
        else:
            method = "regex"

        return MaskingResult(
            text=working_text,
            method=method,
            replacements=replacements,
            applied_presidio=applied_presidio,
            applied_regex=regex_replacements > 0,
            pattern_hits=dict(regex_hits),
            warnings=warnings,
        )

    def _apply_regex_fallback(self, text: str) -> tuple[str, Counter[str], int]:
        masked = text
        hits: Counter[str] = Counter()
        replacements = 0

        for label, pattern, replacement in self.REGEX_RULES:
            masked, count = pattern.subn(replacement, masked)
            if count:
                hits[label] += count
                replacements += count

        return masked, hits, replacements
