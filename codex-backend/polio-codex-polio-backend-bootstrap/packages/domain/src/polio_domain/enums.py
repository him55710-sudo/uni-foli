from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ProjectStatus(StrEnum):
    IDEA = "idea"
    ACTIVE = "active"
    ARCHIVED = "archived"


class UploadStatus(StrEnum):
    RECEIVED = "received"
    STORED = "stored"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class DraftStatus(StrEnum):
    OUTLINE = "outline"
    IN_PROGRESS = "in_progress"
    READY_FOR_RENDER = "ready_for_render"
    ARCHIVED = "archived"


class RenderFormat(StrEnum):
    PDF = "pdf"
    PPTX = "pptx"
    HWPX = "hwpx"


class RenderStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
