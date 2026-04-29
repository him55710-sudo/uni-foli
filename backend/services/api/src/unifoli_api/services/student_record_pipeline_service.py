import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .student_record_page_classifier_service import StudentRecordPageClassifierService
from .student_record_section_parser_service import StudentRecordSectionParserService
from .student_record_normalizer_service import StudentRecordNormalizerService
from .student_record_quality_service import StudentRecordQualityService
from .student_record_chunking_service import StudentRecordChunkingService
from .student_record_ir_service import StudentRecordIRService
from .student_record_block_registry_service import StudentRecordBlockRegistryService
from .student_record_audit_service import StudentRecordAuditService
from .student_record_block_fact_service import StudentRecordBlockFactService
from .student_record_link_graph_service import StudentRecordLinkGraphService
from .student_record_judgement_service import StudentRecordJudgementService

logger = logging.getLogger(__name__)

class StudentAnalysisArtifact(BaseModel):
    """
    The canonical output of the semantic parsing pipeline.
    This artifact is stored in ParsedDocument.parse_metadata["analysis_artifact"].
    """
    canonical_data: Optional[Dict[str, Any]] = None  # StudentRecordCanonicalSchema as dict
    quality_report: Optional[Dict[str, Any]] = None
    chunks: Optional[List[Dict[str, Any]]] = None
    version: str = "2.1.0"
    parsing_metadata: Dict[str, Any]
    stages_success: Dict[str, bool] = {}
    stage_errors: Dict[str, str] = {}
    sr_full_fidelity: Optional[Dict[str, Any]] = None

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
        self.ir_service = StudentRecordIRService()
        self.registry_service = StudentRecordBlockRegistryService()
        self.audit_service = StudentRecordAuditService()
        self.fact_service = StudentRecordBlockFactService()
        self.graph_service = StudentRecordLinkGraphService()
        self.judgement_service = StudentRecordJudgementService()

    def process_document(
        self,
        pages: List[Any],
        raw_text: str,
        heartbeat_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Runs the full semantic parsing pipeline.
        
        Args:
            pages: List of page objects from pdfplumber extraction.
            raw_text: Full concatenated text of the document.
            
        Returns:
            A dictionary equivalent to StudentAnalysisArtifact.
        """
        stages_success = {
            "classification": False,
            "parsing": False,
            "normalization": False,
            "quality": False,
            "chunking": False,
            "ir_generation": False,
            "registry_building": False,
            "fact_extraction": False,
            "graph_building": False,
            "judgement_generation": False,
            "fidelity_audit": False
        }
        stage_errors = {}
        
        canonical_data = None
        quality_report = None
        chunks = []
        sections = []
        classified_pages = []

        logger.info(f"Starting semantic parsing pipeline for document with {len(pages)} pages")

        # 1. Page Classification
        try:
            classified_pages = self.classifier.classify_pages(pages)
            stages_success["classification"] = True
            logger.info("Step 1: Page classification complete")
            if heartbeat_callback:
                try:
                    heartbeat_callback(stage="classification", message="학생부 구성 요소를 분석 중입니다...")
                except TypeError:
                    heartbeat_callback()
        except Exception as e:
            stage_errors["classification"] = str(e)
            logger.error(f"Step 1 Failed: {str(e)}")

        # 2. Section Parsing (Segmentation)
        if stages_success["classification"]:
            try:
                sections = self.parser.parse_sections(classified_pages)
                stages_success["parsing"] = True
                logger.info(f"Step 2: Section parsing complete. Found {len(sections)} sections.")
                if heartbeat_callback:
                    try:
                        heartbeat_callback(stage="parsing", message="상세 활동 내역을 추출 중입니다...")
                    except TypeError:
                        heartbeat_callback()
            except Exception as e:
                stage_errors["parsing"] = str(e)
                logger.error(f"Step 2 Failed: {str(e)}")

        # 3. Data Normalization
        if stages_success["parsing"]:
            try:
                canonical_data_obj = self.normalizer.normalize_sections(sections)
                canonical_data = canonical_data_obj.dict() if hasattr(canonical_data_obj, 'dict') else canonical_data_obj
                stages_success["normalization"] = True
                logger.info("Step 3: Normalization complete")
                if heartbeat_callback:
                    try:
                        heartbeat_callback(stage="normalization", message="데이터 정규화 및 무결성을 검증 중입니다...")
                    except TypeError:
                        heartbeat_callback()
            except Exception as e:
                stage_errors["normalization"] = str(e)
                logger.error(f"Step 3 Failed: {str(e)}")

        # 4. Quality Control
        if stages_success["normalization"]:
            try:
                quality_report = self.quality_service.evaluate_quality(canonical_data_obj if 'canonical_data_obj' in locals() else canonical_data, sections)
                stages_success["quality"] = True
                logger.info(f"Step 4: Quality evaluation complete. Score: {quality_report.get('overall_score')}")
            except Exception as e:
                stage_errors["quality"] = str(e)
                logger.error(f"Step 4 Failed: {str(e)}")

        # 5. Semantic Chunking
        if stages_success["normalization"]: # We can chunk even if quality check fails
            try:
                chunks = self.chunker.create_chunks(canonical_data_obj if 'canonical_data_obj' in locals() else canonical_data)
                stages_success["chunking"] = True
                logger.info(f"Step 5: Semantic chunking complete. Generated {len(chunks)} chunks.")
            except Exception as e:
                stage_errors["chunking"] = str(e)
                logger.error(f"Step 5 Failed: {str(e)}")

        # 6. Full-Fidelity IR Generation
        ir_doc = None
        sr_full_fidelity = None
        try:
            ir_doc = self.ir_service.create_ir(pages)
            stages_success["ir_generation"] = True
            
            # 7. Block Registry Building
            registry = self.registry_service.build_registry(ir_doc)
            stages_success["registry_building"] = True
            
            # 8. Block Fact Extraction
            facts = self.fact_service.extract_facts(registry.blocks)
            stages_success["fact_extraction"] = True
            
            # 9. Link Graph Building
            graph = self.graph_service.build_graph(registry.blocks, facts)
            stages_success["graph_building"] = True
            
            # 10. Judgement Generation (Preliminary)
            judgements = self.judgement_service.generate_judgements(registry, graph)
            stages_success["judgement_generation"] = True
            
            # 11. Fidelity Audit
            audit = self.audit_service.generate_coverage_audit(registry, set([b.id for b in registry.blocks]))
            stages_success["fidelity_audit"] = True
            
            sr_full_fidelity = {
                "ir_document": ir_doc.dict(),
                "block_registry": registry.dict(),
                "block_facts": [f.dict() for f in facts],
                "link_graph": graph.dict(),
                "judgements": [j.dict() for j in judgements],
                "full_coverage_audit": audit.dict(),
                "version": "1.1.0"
            }
            logger.info("Steps 6-11: Full-fidelity pipeline steps complete")
        except Exception as e:
            stage_errors["full_fidelity"] = str(e)
            logger.error(f"Full-fidelity stages failed: {str(e)}")

        # Construct final artifact
        artifact = StudentAnalysisArtifact(
            canonical_data=canonical_data,
            quality_report=quality_report,
            chunks=chunks,
            stages_success=stages_success,
            stage_errors=stage_errors,
            parsing_metadata={
                "page_count": len(pages),
                "section_count": len(sections),
                "classification_summary": self._get_classification_summary(classified_pages) if classified_pages else {},
                "block_count": sr_full_fidelity["block_registry"]["total_blocks"] if sr_full_fidelity else 0,
                
                # Task 2: Structural metadata
                "student_record_structure": self._get_structure_summary(sections),
                "section_coverage": self._calculate_section_coverage(found_categories=found_categories if 'found_categories' in locals() else [], sections=sections, quality_report=quality_report),
                "anchor_registry": self._build_anchor_registry(sr_full_fidelity),
                "parse_quality": {
                    "overall_score": quality_report.get("overall_score", 0.0) if quality_report else 0.0,
                    "text_coverage_score": quality_report.get("text_coverage_score", 0.0) if quality_report else 0.0,
                    "section_coverage_score": quality_report.get("section_coverage_score", 0.0) if quality_report else 0.0,
                    "is_provisional": quality_report.get("is_provisional", False) if quality_report else True,
                    "missing_critical_sections": quality_report.get("missing_critical_sections", []) if quality_report else [],
                    "warnings": quality_report.get("warnings", []) if quality_report else ["Parsing quality assessment unavailable."]
                }
            },
            sr_full_fidelity=sr_full_fidelity
        )

        return artifact.dict()

    def _get_structure_summary(self, sections: List[Any]) -> Dict[str, Any]:
        return {
            "total_sections": len(sections),
            "sections": [
                {
                    "type": getattr(s, "section_type", "unknown").value if hasattr(getattr(s, "section_type", None), 'value') else str(getattr(s, "section_type", "unknown")),
                    "pages": list(range(int(getattr(s, "start_page", 1)), int(getattr(s, "end_page", 1)) + 1))
                } for s in sections
            ]
        }

    def _calculate_section_coverage(self, found_categories: List[Any], sections: List[Any], quality_report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        coverage = {}
        for section in sections:
            s_type = getattr(section, "section_type", "unknown")
            s_key = s_type.value if hasattr(s_type, 'value') else str(s_type)
            if s_key not in coverage:
                coverage[s_key] = {
                    "present": True,
                    "confidence": 0.8,
                    "evidence_count": 1,
                    "pages": list(range(int(getattr(section, "start_page", 1)), int(getattr(section, "end_page", 1)) + 1))
                }
            else:
                coverage[s_key]["evidence_count"] += 1
                coverage[s_key]["pages"].extend(list(range(int(getattr(section, "start_page", 1)), int(getattr(section, "end_page", 1)) + 1)))
                coverage[s_key]["pages"] = list(set(coverage[s_key]["pages"]))
        
        return coverage

    def _build_anchor_registry(self, sr_full_fidelity: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not sr_full_fidelity or "block_registry" not in sr_full_fidelity:
            return []
        
        anchors = []
        blocks = sr_full_fidelity["block_registry"].get("blocks", [])
        for i, block in enumerate(blocks[:50]): # Limit to 50 anchors for performance
            anchors.append({
                "id": block.get("id", str(i)),
                "page_number": block.get("page_number", 1),
                "section": block.get("section_label", "unknown"),
                "label": block.get("block_type", "text"),
                "quote": (block.get("content", "")[:200]),
                "char_start": block.get("char_start", 0),
                "char_end": block.get("char_end", 0),
                "confidence": 0.9
            })
        return anchors

    def _get_classification_summary(self, classified_pages: List[Any]) -> Dict[str, int]:
        summary = {}
        for p in classified_pages:
            ptype = p.page_type.value if hasattr(p, 'page_type') else "unknown"
            summary[ptype] = summary.get(ptype, 0) + 1
        return summary
