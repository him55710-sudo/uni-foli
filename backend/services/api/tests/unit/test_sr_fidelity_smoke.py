import pytest
from unittest.mock import MagicMock
from unifoli_api.services.student_record_ir_service import StudentRecordIRService
from unifoli_api.services.student_record_block_registry_service import StudentRecordBlockRegistryService
from unifoli_api.services.student_record_audit_service import StudentRecordAuditService

def test_pipeline_fidelity_coverage():
    # Mock pdfplumber pages
    mock_pages = []
    for i in range(1, 6): # 5 pages
        page = MagicMock()
        page.page_number = i
        page.width = 595.0
        page.height = 842.0
        page.extract_text_lines.return_value = [
            {"text": f"Page {i} Line 1", "x0": 10, "top": 10, "x1": 100, "bottom": 20},
            {"text": f"Page {i} Line 2", "x0": 10, "top": 30, "x1": 100, "bottom": 40}
        ]
        mock_pages.append(page)
    
    # 1. IR Generation
    ir_service = StudentRecordIRService()
    ir_doc = ir_service.create_ir(mock_pages)
    
    assert ir_doc.total_pages == 5
    assert len(ir_doc.pages) == 5
    assert len(ir_doc.pages[0].blocks) == 2
    
    # 2. Block Registry
    registry_service = StudentRecordBlockRegistryService()
    registry = registry_service.build_registry(ir_doc)
    
    assert registry.total_blocks == 10 # 5 pages * 2 blocks
    assert registry.blocks[0].id == "blk_p1_0"
    
    # 3. Fidelity Audit
    audit_service = StudentRecordAuditService()
    # Assume we processed all blocks
    covered_ids = {b.id for b in registry.blocks}
    audit = audit_service.generate_coverage_audit(registry, covered_ids)
    
    assert audit.coverage_percentage == 100.0
    assert audit.covered_blocks == 10
    assert len(audit.missing_block_ids) == 0

if __name__ == "__main__":
    pytest.main([__file__])
