from dataclasses import dataclass, field

from polio_domain.enums import RenderFormat


@dataclass(slots=True)
class RenderBuildContext:
    project_id: str
    project_title: str
    draft_id: str
    draft_title: str
    render_format: RenderFormat
    content_markdown: str
    requested_by: str | None
    job_id: str
    authenticity_log_lines: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RenderArtifact:
    absolute_path: str
    relative_path: str
    message: str
