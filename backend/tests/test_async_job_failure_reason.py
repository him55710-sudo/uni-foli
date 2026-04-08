from types import SimpleNamespace

from polio_api.services.async_job_service import _public_failure_reason
from polio_domain.enums import AsyncJobType


def test_diagnosis_public_failure_reason_surfaces_parse_hint() -> None:
    job = SimpleNamespace(job_type=AsyncJobType.DIAGNOSIS.value)

    reason = _public_failure_reason(
        job,
        "Parsed document content is empty. Re-run parsing with a clearer source file.",
    )

    assert "Re-run parsing" in reason
    assert "Diagnosis requires parsed text evidence" in reason
