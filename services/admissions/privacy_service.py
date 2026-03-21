from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
import subprocess
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, get_settings
from app.core.redaction import redact_mapping, redact_text_for_logs
from db.models.security import PrivacyScan, Tenant
from domain.enums import PrivacyMaskingMode, PrivacyScanStatus
from services.admissions.utils import ensure_uuid


PHONE_PATTERN = re.compile(r"(01[016789]|02|0[3-9][0-9])[- ]?\d{3,4}[- ]?\d{4}")
EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
RRN_PATTERN = re.compile(r"\b\d{6}[- ]?[1-4]\d{6}\b")


@dataclass(slots=True)
class PrivacyFinding:
    entity_type: str
    start: int
    end: int
    score: float
    text: str


@dataclass(slots=True)
class PrivacyMaskingResult:
    masked_text: str
    index_text: str
    pii_detected: bool
    entity_count: int
    findings: list[dict[str, object]]
    engine_name: str
    status: PrivacyScanStatus
    scan_id: UUID | None = None


class PrivacyService:
    def scan_and_mask(
        self,
        session: Session,
        *,
        tenant: Tenant,
        route_name: str,
        text: str,
        student_file_id=None,
        student_artifact_id=None,
    ) -> PrivacyMaskingResult:
        mode = tenant.masking_mode
        if not text.strip() or mode == PrivacyMaskingMode.OFF or not tenant.pii_detection_enabled:
            result = PrivacyMaskingResult(
                masked_text=text,
                index_text=text,
                pii_detected=False,
                entity_count=0,
                findings=[],
                engine_name="disabled",
                status=PrivacyScanStatus.SKIPPED,
            )
            scan = self._persist_scan(
                session,
                tenant=tenant,
                route_name=route_name,
                text=text,
                result=result,
                student_file_id=student_file_id,
                student_artifact_id=student_artifact_id,
            )
            result.scan_id = scan.id
            return result

        result = self._run_presidio_helper(text, mode=mode)
        if result is None and get_settings().presidio_allow_regex_fallback:
            result = self._regex_detect_and_mask(text, mode=mode)
        if result is None:
            result = PrivacyMaskingResult(
                masked_text=text,
                index_text=text,
                pii_detected=False,
                entity_count=0,
                findings=[],
                engine_name="unavailable",
                status=PrivacyScanStatus.FAILED,
            )

        scan = self._persist_scan(
            session,
            tenant=tenant,
            route_name=route_name,
            text=text,
            result=result,
            student_file_id=student_file_id,
            student_artifact_id=student_artifact_id,
        )
        result.scan_id = scan.id
        return result

    def mask_for_logs(self, text: str) -> str:
        return redact_text_for_logs(text)

    def redact_log_payload(self, payload: dict[str, object]) -> dict[str, object]:
        return redact_mapping(payload)

    def list_privacy_scans(self, session: Session, *, tenant_id=None, student_file_id=None) -> list[PrivacyScan]:
        stmt = select(PrivacyScan).where(PrivacyScan.deleted_at.is_(None)).order_by(PrivacyScan.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(PrivacyScan.tenant_id == ensure_uuid(tenant_id))
        if student_file_id is not None:
            stmt = stmt.where(PrivacyScan.student_file_id == ensure_uuid(student_file_id))
        return list(session.scalars(stmt))

    def _persist_scan(
        self,
        session: Session,
        *,
        tenant: Tenant,
        route_name: str,
        text: str,
        result: PrivacyMaskingResult,
        student_file_id,
        student_artifact_id,
    ) -> PrivacyScan:
        scan = PrivacyScan(
            tenant_id=tenant.id,
            student_file_id=ensure_uuid(student_file_id),
            student_artifact_id=ensure_uuid(student_artifact_id),
            route_name=route_name,
            masking_mode=tenant.masking_mode,
            status=result.status,
            pii_detected=result.pii_detected,
            entity_count=result.entity_count,
            raw_text_sha256=sha256(text.encode("utf-8")).hexdigest(),
            masked_preview=result.masked_text[:200],
            findings_json={"findings": self._sanitize_findings(result.findings)},
            metadata_json={"engine_name": result.engine_name},
        )
        session.add(scan)
        session.flush()
        return scan

    def _run_presidio_helper(self, text: str, *, mode: PrivacyMaskingMode) -> PrivacyMaskingResult | None:
        settings = get_settings()
        if not settings.presidio_enabled or not settings.presidio_helper_python:
            return None
        helper_script = PROJECT_ROOT / "scripts" / "presidio_masking_helper.py"
        if not helper_script.exists():
            return None
        payload = {"text": text}
        try:
            process = subprocess.run(
                [settings.presidio_helper_python, str(helper_script)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=settings.presidio_helper_timeout_seconds,
                check=True,
            )
        except Exception:
            return None
        if not process.stdout.strip():
            return None
        response = json.loads(process.stdout)
        findings = self._sanitize_findings(response.get("findings", []))
        masked_text = response.get("masked_text", text)
        pii_detected = bool(findings)
        index_text = masked_text if mode in {PrivacyMaskingMode.MASK_FOR_INDEX, PrivacyMaskingMode.MASK_ALL} else text
        return PrivacyMaskingResult(
            masked_text=masked_text,
            index_text=index_text,
            pii_detected=pii_detected,
            entity_count=len(findings),
            findings=findings,
            engine_name="presidio_helper",
            status=PrivacyScanStatus.SUCCEEDED,
        )

    def _regex_detect_and_mask(self, text: str, *, mode: PrivacyMaskingMode) -> PrivacyMaskingResult:
        findings: list[PrivacyFinding] = []
        for entity_type, pattern in (
            ("PHONE_NUMBER", PHONE_PATTERN),
            ("EMAIL_ADDRESS", EMAIL_PATTERN),
            ("KOREAN_RRN", RRN_PATTERN),
        ):
            for match in pattern.finditer(text):
                findings.append(
                    PrivacyFinding(
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        score=0.85,
                        text=match.group(0),
                    )
                )
        findings.sort(key=lambda item: item.start)
        masked_text = self._apply_masks(text, findings)
        index_text = masked_text if mode in {PrivacyMaskingMode.MASK_FOR_INDEX, PrivacyMaskingMode.MASK_ALL} else text
        return PrivacyMaskingResult(
            masked_text=masked_text,
            index_text=index_text,
            pii_detected=bool(findings),
            entity_count=len(findings),
            findings=[
                {
                    "entity_type": finding.entity_type,
                    "start": finding.start,
                    "end": finding.end,
                    "score": finding.score,
                    "match_preview": self._preview_entity_text(finding.text),
                }
                for finding in findings
            ],
            engine_name="regex_fallback",
            status=PrivacyScanStatus.SUCCEEDED,
        )

    def _apply_masks(self, text: str, findings: list[PrivacyFinding]) -> str:
        if not findings:
            return text
        output: list[str] = []
        cursor = 0
        for finding in findings:
            output.append(text[cursor : finding.start])
            output.append(f"<{finding.entity_type}>")
            cursor = finding.end
        output.append(text[cursor:])
        return "".join(output)

    def _sanitize_findings(self, findings: list[dict[str, object]]) -> list[dict[str, object]]:
        sanitized: list[dict[str, object]] = []
        for finding in findings:
            item = dict(finding)
            if "text" in item and isinstance(item["text"], str):
                item["match_preview"] = self._preview_entity_text(item["text"])
                item.pop("text", None)
            sanitized.append(item)
        return sanitized

    def _preview_entity_text(self, text: str) -> str:
        if len(text) <= 4:
            return "*" * len(text)
        return f"{text[:2]}***{text[-2:]}"


privacy_service = PrivacyService()
