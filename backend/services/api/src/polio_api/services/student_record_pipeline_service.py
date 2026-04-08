import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .student_record_page_classifier_service import StudentRecordPageClassifierService
from .student_record_section_parser_service import StudentRecordSectionParserService
from .student_record_normalizer_service import StudentRecordNormalizerService
from .student_record_quality_service import StudentRecordQualityService
from .student_record_chunking_service import StudentRecordChunkingService

logger = logging.getLogger(__name__)

class StudentAnalysisArtifact(BaseModel):
    """
    The canonical output of the semantic parsing pipeline.
    This artifact is stored in ParsedDocument.parse_metadata["analysis_artifact"].
    """
    canonical_data: Dict[str, Any]  # StudentRecordCanonicalSchema as dict
    quality_report: Dict[str, Any]
    chunks: List[Dict[str, Any]]
    version: str = "2.0.0"
    parsing_metadata: Dict[str, Any]

class StudentRecordPipelineService:
    """
    Orchestrator for the advanced student record parsing pipeline.
    This service replaces the simple text extraction with a structured,
    layout-aware semantic parsing flow.
    """

    def __init__(self):
        self.classifier = StudentRecordPageClassifierService()
        self.parser = StudentRecordSectionParserService()
        self.normalizer = StudentRecordNormalizerService()
        self.quality_service = StudentRecordQualityService()
        self.chunker = StudentRecordChunkingService()

    def process_document(self, pages: List[Any], raw_text: str) -> Dict[str, Any]:
        """
        Runs the full semantic parsing pipeline.
        
        Args:
            pages: List of page objects from pdfplumber extraction.
            raw_text: Full concatenated text of the document.
            
        Returns:
            A dictionary equivalent to StudentAnalysisArtifact.
        """
        try:
            logger.info(f"Starting semantic parsing pipeline for document with {len(pages)} pages")

            # 1. Page Classification
            classified_pages = self.classifier.classify_pages(pages)
            logger.info("Step 1: Page classification complete")

            # 2. Section Parsing (Segmentation)
            sections = self.parser.parse_sections(classified_pages)
            logger.info(f"Step 2: Section parsing complete. Found {len(sections)} sections.")

            # 3. Data Normalization
            canonical_data = self.normalizer.normalize_sections(sections)
            logger.info("Step 3: Normalization complete")

            # 4. Quality Control
            quality_report = self.quality_service.evaluate_quality(canonical_data, sections)
            logger.info(f"Step 4: Quality evaluation complete. Score: {quality_report.get('overall_score')}")

            # 5. Semantic Chunking
            chunks = self.chunker.create_chunks(canonical_data)
            logger.info(f"Step 5: Semantic chunking complete. Generated {len(chunks)} chunks.")

            # Construct final artifact
            artifact = StudentAnalysisArtifact(
                canonical_data=canonical_data.dict(),
                quality_report=quality_report,
                chunks=chunks,
                parsing_metadata={
                    "page_count": len(pages),
                    "section_count": len(sections),
                    "classification_summary": self._get_classification_summary(classified_pages)
                }
            )

            return artifact.dict()

        except Exception as e:
            logger.exception(f"Error in StudentRecordPipelineService: {str(e)}")
            # Return basic fallback or re-raise depending on integration requirements
            raise

    def _get_classification_summary(self, classified_pages: List[Any]) -> Dict[str, int]:
        summary = {}
        for p in classified_pages:
            ptype = p.page_type.value if hasattr(p, 'page_type') else "unknown"
            summary[ptype] = summary.get(ptype, 0) + 1
        return summary
