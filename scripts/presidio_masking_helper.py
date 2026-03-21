from __future__ import annotations

import json
import re
import sys

from presidio_analyzer import RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


PATTERNS = {
    "PHONE_NUMBER": re.compile(r"(01[016789]|02|0[3-9][0-9])[- ]?\d{3,4}[- ]?\d{4}"),
    "EMAIL_ADDRESS": re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
    "KOREAN_RRN": re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b"),
}


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    text = str(payload.get("text", ""))
    findings: list[dict[str, object]] = []
    results: list[RecognizerResult] = []
    for entity_type, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(
                {
                    "entity_type": entity_type,
                    "start": match.start(),
                    "end": match.end(),
                    "score": 0.9,
                    "text": match.group(0),
                }
            )
            results.append(
                RecognizerResult(
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    score=0.9,
                )
            )

    operators = {
        entity_type: OperatorConfig("replace", {"new_value": f"<{entity_type}>"})
        for entity_type in PATTERNS
    }
    anonymizer = AnonymizerEngine()
    masked_text = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators).text
    sys.stdout.write(json.dumps({"masked_text": masked_text, "findings": findings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
