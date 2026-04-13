from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AsyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None
    job_type: str
    resource_type: str
    resource_id: str
    status: str
    retry_count: int
    max_retries: int
    failure_reason: str | None
    failure_history: list[dict[str, object]]
    progress_stage: str | None = None
    progress_message: str | None = None
    progress_percent: float | None = None
    progress_history: list[dict[str, object]] = Field(default_factory=list)
    next_attempt_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    dead_lettered_at: datetime | None
    created_at: datetime
    updated_at: datetime


def as_async_job_read(job: object) -> AsyncJobRead:
    base = AsyncJobRead.model_validate(job)
    payload = getattr(job, "payload", None)
    if isinstance(payload, dict):
        percent = payload.get("progress_percent")
        if isinstance(percent, (int, float)):
            base.progress_percent = float(percent)
        history = payload.get("progress_history")
        if isinstance(history, list):
            normalized_history: list[dict[str, object]] = []
            for item in history:
                if not isinstance(item, dict):
                    continue
                stage = str(item.get("stage") or "").strip()
                message = str(item.get("message") or "").strip()
                completed_at = str(item.get("completed_at") or "").strip()
                if not stage and not message:
                    continue
                normalized_history.append(
                    {
                        "stage": stage or "stage",
                        "message": message or "",
                        "completed_at": completed_at or "",
                    }
                )
            base.progress_history = normalized_history[-20:]
    return base

