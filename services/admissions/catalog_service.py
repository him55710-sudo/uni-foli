from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.admissions import EvaluationDimension, University
from db.models.catalog import (
    AdmissionCycleAlias,
    DocumentTypeLabel,
    EvaluationDimensionAlias,
    SourceTierExample,
    UniversityAlias,
    UniversityUnitAlias,
)
from domain.enums import CycleType, DocumentType, EvaluationDimensionCode, SourceTier


DEFAULT_EVALUATION_DIMENSIONS = [
    (
        EvaluationDimensionCode.ACADEMIC_COMPETENCE,
        "학업역량",
        "Academic Competence",
        "교과 학습, 탐구, 분석, 지속적 성장에서 드러나는 학업 수행 역량",
        ["학업역량", "교과 역량", "학업 능력"],
    ),
    (
        EvaluationDimensionCode.SELF_DIRECTED_GROWTH,
        "자기주도성장",
        "Self Directed Growth",
        "기획, 설계, 수정, 보완을 통해 드러나는 자기주도적 성장",
        ["자기주도성장", "자기주도", "주도적 성장"],
    ),
    (
        EvaluationDimensionCode.CAREER_EXPLORATION,
        "진로탐색",
        "Career Exploration",
        "전공과 진로에 대한 탐색 과정과 구체적 이해",
        ["진로탐색", "진로 탐구", "진로 역량"],
    ),
    (
        EvaluationDimensionCode.MAJOR_FIT,
        "전공적합성",
        "Major Fit",
        "희망 전공과 활동 사이의 정합성과 심화 정도",
        ["전공적합성", "전공 적합성", "전공 연계"],
    ),
    (
        EvaluationDimensionCode.COMMUNITY_CONTRIBUTION,
        "공동체역량",
        "Community Contribution",
        "협업과 공동체 기여를 통해 드러나는 태도와 역할",
        ["공동체역량", "협업", "공동체 기여"],
    ),
    (
        EvaluationDimensionCode.EVIDENCE_QUALITY,
        "근거품질",
        "Evidence Quality",
        "서술의 구체성, 검증 가능성, 근거의 밀도",
        ["근거품질", "근거 질", "증거 품질"],
    ),
    (
        EvaluationDimensionCode.AUTHENTICITY,
        "진정성",
        "Authenticity",
        "활동과 기록이 실제 경험을 기반으로 하는지 여부",
        ["진정성", "authenticity", "실제성"],
    ),
]

DEFAULT_CYCLE_ALIASES = [
    ("수시", "수시", CycleType.SUSI.value, None, True),
    ("학생부종합전형", "학생부종합전형", CycleType.SUSI.value, None, True),
    ("정시", "정시", CycleType.JEONGSI.value, None, False),
    ("regular", "regular", CycleType.REGULAR.value, None, False),
]

DEFAULT_DOCUMENT_TYPE_LABELS = [
    ("모집요강", DocumentType.GUIDEBOOK),
    ("전형요강", DocumentType.GUIDEBOOK),
    ("faq", DocumentType.FAQ),
    ("자주 묻는 질문", DocumentType.FAQ),
    ("평가기준", DocumentType.EVALUATION_GUIDE),
    ("평가요소", DocumentType.EVALUATION_GUIDE),
    ("설명회", DocumentType.BRIEFING_MATERIAL),
    ("공지", DocumentType.ANNOUNCEMENT),
    ("시행계획", DocumentType.POLICY),
    ("학교생활기록부", DocumentType.SCHOOL_RECORD_GUIDE),
]

DEFAULT_SOURCE_TIER_EXAMPLES = [
    (
        SourceTier.TIER_1_OFFICIAL,
        "대학교 입학처 모집요강 PDF",
        "대학 공식 입학처가 직접 배포한 자료로 최고 신뢰 source tier에 해당한다.",
    ),
    (
        SourceTier.TIER_2_PUBLIC_SUPPORT,
        "공공 교육 포털의 입시 해설 자료",
        "공공성이 높지만 대학 개별 규정은 아니므로 보조 설명 자료로 사용한다.",
    ),
    (
        SourceTier.TIER_3_CONTROLLED_SECONDARY,
        "신뢰 가능한 교육 전문지 해설 기사",
        "보조 해설로는 유용하지만 공식 규칙보다 우선하면 안 된다.",
    ),
]


class CatalogService:
    def bootstrap_reference_data(self, session: Session) -> None:
        self._bootstrap_evaluation_dimensions(session)
        self._bootstrap_cycle_aliases(session)
        self._bootstrap_document_type_labels(session)
        self._bootstrap_source_tier_examples(session)
        session.flush()

    def canonicalize_university_name(self, session: Session, raw_name: str | None) -> University | None:
        if not raw_name:
            return None
        normalized = raw_name.strip()
        university = session.scalar(select(University).where(University.name_ko == normalized))
        if university is not None:
            return university
        alias = session.scalar(select(UniversityAlias).where(UniversityAlias.alias_text == normalized))
        if alias is not None:
            return alias.university
        return None

    def normalize_cycle_label(self, session: Session, raw_label: str | None) -> tuple[str | None, str | None]:
        if not raw_label:
            return None, None
        alias = session.scalar(select(AdmissionCycleAlias).where(AdmissionCycleAlias.alias_text == raw_label.strip()))
        if alias is not None:
            return alias.normalized_label, alias.cycle_type
        return raw_label.strip(), None

    def classify_document_type(self, session: Session, haystack: str) -> DocumentType | None:
        normalized = haystack.lower()
        labels = list(session.scalars(select(DocumentTypeLabel)))
        for label in labels:
            label_text = label.label_text.lower()
            if label.match_mode == "contains" and label_text in normalized:
                return label.document_type
            if label.match_mode == "exact" and label_text == normalized:
                return label.document_type
        return None

    def list_source_tier_examples(self, session: Session) -> list[SourceTierExample]:
        return list(session.scalars(select(SourceTierExample).order_by(SourceTierExample.created_at.desc())))

    def list_document_type_labels(self, session: Session) -> list[DocumentTypeLabel]:
        return list(session.scalars(select(DocumentTypeLabel).order_by(DocumentTypeLabel.label_text.asc())))

    def list_admission_cycle_aliases(self, session: Session) -> list[AdmissionCycleAlias]:
        return list(session.scalars(select(AdmissionCycleAlias).order_by(AdmissionCycleAlias.alias_text.asc())))

    def list_university_aliases(self, session: Session) -> list[UniversityAlias]:
        return list(session.scalars(select(UniversityAlias).order_by(UniversityAlias.alias_text.asc())))

    def list_university_unit_aliases(self, session: Session) -> list[UniversityUnitAlias]:
        return list(session.scalars(select(UniversityUnitAlias).order_by(UniversityUnitAlias.source_text.asc())))

    def _bootstrap_evaluation_dimensions(self, session: Session) -> None:
        for code, name_ko, name_en, description, aliases in DEFAULT_EVALUATION_DIMENSIONS:
            dimension = session.scalar(select(EvaluationDimension).where(EvaluationDimension.code == code))
            if dimension is None:
                dimension = EvaluationDimension(
                    code=code,
                    name_ko=name_ko,
                    name_en=name_en,
                    description=description,
                    is_global_default=True,
                    metadata_json={},
                )
                session.add(dimension)
                session.flush()
            for alias_text in aliases:
                if session.scalar(select(EvaluationDimensionAlias).where(EvaluationDimensionAlias.alias_text == alias_text)) is None:
                    session.add(
                        EvaluationDimensionAlias(
                            evaluation_dimension_id=dimension.id,
                            alias_text=alias_text,
                            language_code="ko",
                            metadata_json={},
                        )
                    )

    def _bootstrap_cycle_aliases(self, session: Session) -> None:
        self._ensure_rows(
            session,
            AdmissionCycleAlias,
            "alias_text",
            [
                {
                    "alias_text": alias_text,
                    "normalized_label": normalized_label,
                    "cycle_type": cycle_type,
                    "admissions_year_hint": admissions_year_hint,
                    "is_current_cycle_hint": is_current_cycle_hint,
                    "metadata_json": {},
                }
                for alias_text, normalized_label, cycle_type, admissions_year_hint, is_current_cycle_hint in DEFAULT_CYCLE_ALIASES
            ],
        )

    def _bootstrap_document_type_labels(self, session: Session) -> None:
        self._ensure_rows(
            session,
            DocumentTypeLabel,
            ("label_text", "language_code"),
            [
                {
                    "label_text": label_text,
                    "document_type": document_type,
                    "language_code": "ko",
                    "match_mode": "contains",
                    "metadata_json": {},
                }
                for label_text, document_type in DEFAULT_DOCUMENT_TYPE_LABELS
            ],
        )

    def _bootstrap_source_tier_examples(self, session: Session) -> None:
        self._ensure_rows(
            session,
            SourceTierExample,
            "example_text",
            [
                {
                    "source_tier": source_tier,
                    "example_text": example_text,
                    "rationale": rationale,
                    "is_positive_example": True,
                    "metadata_json": {},
                }
                for source_tier, example_text, rationale in DEFAULT_SOURCE_TIER_EXAMPLES
            ],
        )

    def _ensure_rows(
        self,
        session: Session,
        model_cls,
        unique_fields: str | tuple[str, ...],
        rows: Iterable[dict[str, object]],
    ) -> None:
        if isinstance(unique_fields, str):
            unique_fields = (unique_fields,)
        for row in rows:
            filters = [getattr(model_cls, field) == row[field] for field in unique_fields]
            if session.scalar(select(model_cls).where(*filters)) is None:
                session.add(model_cls(**row))


catalog_service = CatalogService()
