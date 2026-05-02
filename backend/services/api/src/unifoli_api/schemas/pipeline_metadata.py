from typing import Any, List, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class BaseParsingMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_count: int = Field(default=0, ge=0)
    table_count: int = Field(default=0, ge=0)
    source_storage_provider: str | None = Field(default=None, max_length=32)
    source_storage_key: str | None = Field(default=None, max_length=600)
    warnings: list[str] = Field(default_factory=list)


class PageFailure(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page_number: int | None = Field(default=None, ge=0)
    message: str = Field(default="", max_length=1000)


class MaskingMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    methods: list[str] = Field(default_factory=list)
    replacement_count: int = Field(default=0, ge=0)
    pattern_hits: dict[str, int] = Field(default_factory=dict)


class PageInsight(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page_number: int = Field(..., gt=0)
    summary: str = Field(..., max_length=1000)
    section_candidates: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)


class SectionCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    pages: list[int] = Field(default_factory=list)


class SectionCoverage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    present: bool = False
    confidence: float = 0.0
    evidence_count: int = 0
    pages: List[int] = Field(default_factory=list)
    warning: Optional[str] = None


class EvidenceAnchor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    page_number: int
    section: str
    label: str
    quote: str
    char_start: int
    char_end: int
    confidence: float


class ParseQuality(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overall_score: float = 0.0
    text_coverage_score: float = 0.0
    table_coverage_score: float = 0.0
    section_coverage_score: float = 0.0
    page_diversity_score: float = 0.0
    anchor_diversity_score: float = 0.0
    missing_critical_sections: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    is_provisional: bool = False


class PdfAnalysisMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    schema_version: str | None = Field(default=None, max_length=80)
    provider: str | None = Field(default=None, max_length=40)
    model: str | None = Field(default=None, max_length=80)
    engine: str | None = Field(default=None, max_length=20)
    
    actual_provider: str | None = Field(default=None, max_length=40)
    actual_model: str | None = Field(default=None, max_length=80)
    pdf_analysis_engine: str | None = Field(default=None, max_length=20)
    
    fallback_used: bool = False
    fallback_reason: str | None = Field(default=None, max_length=220)
    
    processing_duration_ms: int = Field(default=0, ge=0)
    generated_at: str | None = Field(default=None, max_length=50)
    
    summary: str | None = Field(default=None, max_length=2000)
    document_type: str | None = Field(default=None, max_length=80)
    source_document_kind: str | None = Field(default=None, max_length=80)
    document_type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    likely_student_record: bool = False
    
    failure_reason: str | None = Field(default=None, max_length=240)
    recovered_from_text_fallback: bool = False
    
    key_points: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    page_insights: list[PageInsight] = Field(default_factory=list)
    section_candidates: dict[str, SectionCandidate] = Field(default_factory=dict)
    ambiguity_notes: list[str] = Field(default_factory=list)
    extraction_limits: list[str] = Field(default_factory=list)


class PipelineMetadata(BaseModel):
    """
    Comprehensive schema for the 'parse_metadata' field in ParsedDocument.
    """
    model_config = ConfigDict(extra="allow")

    # Base parsing info
    chunk_count: int = Field(default=0, ge=0)
    table_count: int = Field(default=0, ge=0)
    source_storage_provider: str | None = Field(default=None)
    source_storage_key: str | None = Field(default=None)
    warnings: list[str] = Field(default_factory=list)
    page_failures: list[PageFailure] = Field(default_factory=list)

    # Task 2: New structural parsing info
    student_record_structure: Optional[Dict[str, Any]] = None
    student_record_canonical: Optional[Dict[str, Any]] = None
    section_coverage: Dict[str, SectionCoverage] = Field(default_factory=dict)
    page_coverage: List[int] = Field(default_factory=list)
    anchor_registry: List[EvidenceAnchor] = Field(default_factory=list)
    parse_quality: Optional[ParseQuality] = None
    provisional_reason: Optional[str] = None

    # Secondary stages
    masking: MaskingMetadata | None = None
    pdf_analysis: PdfAnalysisMetadata | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineMetadata":
        return cls.model_validate(data)
