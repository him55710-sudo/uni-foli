from __future__ import annotations

from typing import Any
from pydantic import BaseModel

from polio_api.services.student_record_page_classifier_service import PageCategory
from polio_api.services.student_record_normalizer_service import StudentRecordCanonicalSchema


class SemanticChunk(BaseModel):
    category: str
    context: str
    content: str
    metadata: dict[str, Any]


class StudentRecordChunkingService:
    """
    Compatibility wrapper used by StudentRecordPipelineService.
    """

    def create_chunks(self, canonical_data: StudentRecordCanonicalSchema | dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(canonical_data, StudentRecordCanonicalSchema):
            canonical = canonical_data
        else:
            canonical = StudentRecordCanonicalSchema.model_validate(canonical_data)
        return [chunk.model_dump() for chunk in create_semantic_chunks(canonical)]


def create_semantic_chunks(canonical: StudentRecordCanonicalSchema) -> list[SemanticChunk]:
    """
    Creates semantic chunks for RAG based on the canonical schema.
    """
    chunks = []
    
    # 1. Attendance Chunk
    if canonical.attendance:
        chunks.append(SemanticChunk(
            category="attendance",
            context="Student attendance records across grades",
            content=f"Attendance: {canonical.attendance}",
            metadata={"type": "structured_data"}
        ))
        
    # 2. Awards Chunks
    for award in canonical.awards:
        chunks.append(SemanticChunk(
            category="awards",
            context=f"Award: {award.award_name}",
            content=f"Received {award.award_name} ({award.grade}) on {award.date} hosted by {award.host}.",
            metadata={"type": "structured_data", "award_name": award.award_name}
        ))
        
    # 3. Extracurricular Narrative Chunks
    for activity_type, text in canonical.extracurricular_narratives.items():
        if len(text) < 20: continue
        chunks.append(SemanticChunk(
            category="extracurricular",
            context=f"Activity Type: {activity_type}",
            content=text,
            metadata={"type": "narrative", "activity_type": activity_type}
        ))
        
    # 4. Subject Special Notes
    for subject, note in canonical.subject_special_notes.items():
        if len(note) < 20: continue
        chunks.append(SemanticChunk(
            category="special_notes",
            context=f"Subject: {subject}",
            content=note,
            metadata={"type": "narrative", "subject": subject}
        ))
        
    # 5. Behavior Opinion
    if canonical.behavior_opinion and len(canonical.behavior_opinion) > 20:
        chunks.append(SemanticChunk(
            category="behavior",
            context="Final comprehensive behavior opinion and summary",
            content=canonical.behavior_opinion,
            metadata={"type": "narrative"}
        ))

    return chunks
