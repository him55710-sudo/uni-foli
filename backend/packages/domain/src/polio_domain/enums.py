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
    MASKING = "masking"
    PARSING = "parsing"
    RETRYING = "retrying"
    PARSED = "parsed"
    PARTIAL = "partial"
    FAILED = "failed"


class DocumentProcessingStatus(StrEnum):
    UPLOADED = "uploaded"
    MASKING = "masking"
    PARSING = "parsing"
    RETRYING = "retrying"
    PARSED = "parsed"
    PARTIAL = "partial"
    FAILED = "failed"


class DocumentMaskingStatus(StrEnum):
    PENDING = "pending"
    MASKING = "masking"
    MASKED = "masked"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"
    RETRYING = "retrying"


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
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkshopStatus(StrEnum):
    IDLE = "idle"
    COLLECTING_CONTEXT = "collecting_context"
    DRAFTING = "drafting"
    RENDERING = "rendering"
    DONE = "done"


class TurnType(StrEnum):
    STARTER = "starter"
    FOLLOW_UP = "follow_up"
    MESSAGE = "message"


class QualityLevel(StrEnum):
    """
    워크샵 결과물의 깊이와 표현 수위를 결정하는 품질 수준.

    LOW  (안전형): 교과 개념 충실, 검증 가능한 사실 위주, 팩트체크 최우선.
                   화려한 표현/심화 이론 금지. 누구나 실제로 해볼 수 있는 수준.
    MID  (표준형): 교과 응용 + 간단한 확장. 일반 학생이 수행했을 법한 범위.
                   참고문헌 1-2개 활용 가능, 소결론 도출 허용.
    HIGH (심화형): 심화 이론 활용 가능하나 반드시 학생 실제 맥락 기반.
                   출처 강제, AI 냄새 감지 시 강등 조치.
    """
    LOW  = "low"
    MID  = "mid"
    HIGH = "high"


class BlockType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"


class EvidenceProvenance(StrEnum):
    STUDENT_RECORD = "STUDENT_RECORD"
    EXTERNAL_RESEARCH = "EXTERNAL_RESEARCH"


class ResearchSourceClassification(StrEnum):
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"
    STUDENT_OWNED_SOURCE = "STUDENT_OWNED_SOURCE"
    EXPERT_COMMENTARY = "EXPERT_COMMENTARY"
    COMMUNITY_POST = "COMMUNITY_POST"
    SCRAPED_OPINION = "SCRAPED_OPINION"


class AsyncJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"


class AsyncJobType(StrEnum):
    DIAGNOSIS = "diagnosis"
    DOCUMENT_PARSE = "document_parse"
    RENDER = "render"
    RESEARCH_INGEST = "research_ingest"


class VisualApprovalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REPLACED = "replaced"
    REMOVED = "removed"
