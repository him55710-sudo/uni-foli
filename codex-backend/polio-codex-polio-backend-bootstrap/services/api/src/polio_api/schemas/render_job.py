from datetime import datetime

from pydantic import BaseModel, ConfigDict

from polio_domain.enums import RenderFormat


class RenderJobCreate(BaseModel):
    project_id: str
    draft_id: str
    render_format: RenderFormat
    requested_by: str | None = None


class RenderJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    draft_id: str
    render_format: str
    status: str
    output_path: str | None
    result_message: str | None
    requested_by: str | None
    created_at: datetime
    updated_at: datetime


class RenderFormatInfo(BaseModel):
    format: RenderFormat
    implementation_level: str
    description: str
