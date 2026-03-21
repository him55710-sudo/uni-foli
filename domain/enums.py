from __future__ import annotations

from enum import StrEnum


class SourceTier(StrEnum):
    TIER_1_OFFICIAL = "tier_1_official"
    TIER_2_PUBLIC_SUPPORT = "tier_2_public_support"
    TIER_3_CONTROLLED_SECONDARY = "tier_3_controlled_secondary"
    TIER_4_EXCLUDED = "tier_4_excluded"


class SourceCategory(StrEnum):
    MINISTRY = "ministry"
    UNIVERSITY = "university"
    PUBLIC_PORTAL = "public_portal"
    EDUCATION_OFFICE = "education_office"
    PUBLIC_INSTITUTION = "public_institution"
    JOURNALISM = "journalism"
    EXPERT_COLUMN = "expert_column"
    OTHER = "other"


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    LOW_TRUST = "low_trust"
    ARCHIVED = "archived"
    FAILED = "failed"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class PrivacyMaskingMode(StrEnum):
    OFF = "off"
    DETECT_ONLY = "detect_only"
    MASK_FOR_INDEX = "mask_for_index"
    MASK_ALL = "mask_all"


class PrivacyScanStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class DeletionMode(StrEnum):
    SOFT_DELETE = "soft_delete"
    HARD_DELETE = "hard_delete"


class DeletionRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class CrawlJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class SourceSeedType(StrEnum):
    HTML_INDEX = "html_index"
    GUIDEBOOK_INDEX = "guidebook_index"
    DIRECT_FILE = "direct_file"
    ANNOUNCEMENT_INDEX = "announcement_index"


class DiscoveredUrlStatus(StrEnum):
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    INGESTED = "ingested"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    EXTRACTING = "extracting"
    INDEXING = "indexing"
    REVIEW_REQUIRED = "review_required"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    REVIEW_REQUIRED = "review_required"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionBatchStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionFailureCode(StrEnum):
    TIMEOUT = "timeout"
    GATEWAY_ERROR = "gateway_error"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    EMPTY_RESPONSE = "empty_response"
    NO_CANDIDATE_CHUNKS = "no_candidate_chunks"
    ALL_BATCHES_FAILED = "all_batches_failed"


class ExtractionChunkDecisionStatus(StrEnum):
    SELECTED = "selected"
    SKIPPED = "skipped"


class DocumentStatus(StrEnum):
    REGISTERED = "registered"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    EXTRACTED = "extracted"
    INDEXED = "indexed"
    LOW_TRUST = "low_trust"
    ARCHIVED = "archived"
    FAILED = "failed"


class FileObjectStatus(StrEnum):
    STORED = "stored"
    QUARANTINED = "quarantined"
    PARSED = "parsed"
    FAILED = "failed"
    DELETED = "deleted"


class StorageProvider(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    REMOTE_URL = "remote_url"


class DocumentType(StrEnum):
    GUIDEBOOK = "guidebook"
    POLICY = "policy"
    ANNOUNCEMENT = "announcement"
    FAQ = "faq"
    EVALUATION_GUIDE = "evaluation_guide"
    COLUMN = "column"
    RECRUITMENT_GUIDE = "recruitment_guide"
    RESULT_SUMMARY = "result_summary"
    BRIEFING_MATERIAL = "briefing_material"
    SCHOOL_RECORD_GUIDE = "school_record_guide"
    OTHER = "other"


class CycleType(StrEnum):
    GENERAL = "general"
    SUSI = "susi"
    JEONGSI = "jeongsi"
    EARLY = "early"
    REGULAR = "regular"


class BlockType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST_ITEM = "list_item"
    FAQ_ITEM = "faq_item"
    FOOTNOTE = "footnote"
    OTHER = "other"


class ClaimType(StrEnum):
    EVALUATION_CRITERION = "evaluation_criterion"
    DOCUMENT_RULE = "document_rule"
    POLICY_STATEMENT = "policy_statement"
    INTERPRETATION_NOTE = "interpretation_note"
    ADMISSIONS_EMPHASIS = "admissions_emphasis"
    ELIGIBILITY_CONDITION = "eligibility_condition"
    CAUTION_RULE = "caution_rule"


class ClaimStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    SUPERSEDED = "superseded"


class ConflictType(StrEnum):
    OUTDATED_VS_CURRENT = "outdated_vs_current"
    OFFICIAL_VS_SECONDARY = "official_vs_secondary"
    UNIVERSITY_VS_GENERAL = "university_vs_general"
    DIRECT_CONTRADICTION = "direct_contradiction"
    SCOPE_MISMATCH = "scope_mismatch"


class ConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FreshnessState(StrEnum):
    CURRENT = "current"
    FRESH = "fresh"
    STALE = "stale"


class RetrievalConflictState(StrEnum):
    NONE = "none"
    OPEN = "open"
    RESOLVED = "resolved"


class RetrievalRecordType(StrEnum):
    BLOCK = "block"
    CLAIM = "claim"


class RetrievalIndexStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class EvaluationDimensionCode(StrEnum):
    ACADEMIC_COMPETENCE = "academic_competence"
    SELF_DIRECTED_GROWTH = "self_directed_growth"
    CAREER_EXPLORATION = "career_exploration"
    MAJOR_FIT = "major_fit"
    COMMUNITY_CONTRIBUTION = "community_contribution"
    EVIDENCE_QUALITY = "evidence_quality"
    AUTHENTICITY = "authenticity"


class StudentFileStatus(StrEnum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    CLASSIFIED = "classified"
    ANALYZED = "analyzed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class StudentArtifactType(StrEnum):
    SCHOOL_RECORD = "school_record"
    INQUIRY_REPORT = "inquiry_report"
    CLUB_PROJECT = "club_project"
    REFLECTION_NOTE = "reflection_note"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class StudentAnalysisRunType(StrEnum):
    EVALUATION_MAPPING = "evaluation_mapping"
    GAP_ANALYSIS = "gap_analysis"
    EVIDENCE_QUALITY = "evidence_quality"
    CHAT_RESPONSE = "chat_response"


class StudentAnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class PolicyFlagCode(StrEnum):
    FABRICATION_REQUEST = "fabrication_request"
    DECEPTIVE_POSITIONING = "deceptive_positioning"
    OUTDATED_SOURCE = "outdated_source"
    SOURCE_CONFLICT = "source_conflict"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LOW_TRUST_SOURCE = "low_trust_source"


class PolicyFlagStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ReviewTaskType(StrEnum):
    DOCUMENT_TRUST_REVIEW = "document_trust_review"
    CLAIM_APPROVAL = "claim_approval"
    EXTRACTION_FAILURE_REVIEW = "extraction_failure_review"
    CONFLICT_RESOLUTION = "conflict_resolution"
    STUDENT_ANALYSIS_REVIEW = "student_analysis_review"
    SAFETY_REVIEW = "safety_review"
    REPROCESS_REQUEST = "reprocess_request"


class ReviewTaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class ResponseTraceKind(StrEnum):
    ANALYSIS = "analysis"
    CHAT = "chat"
    REVIEW = "review"


class EvalExampleKind(StrEnum):
    GOLD_CLAIM = "gold_claim"
    BAD_CLAIM = "bad_claim"
    EVIDENCE_SPAN = "evidence_span"
    UNSAFE_PROMPT = "unsafe_prompt"
    WEAK_EVIDENCE = "weak_evidence"
