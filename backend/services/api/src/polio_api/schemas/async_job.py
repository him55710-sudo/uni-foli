from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    next_attempt_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    dead_lettered_at: datetime | None
    created_at: datetime
    updated_at: datetime

