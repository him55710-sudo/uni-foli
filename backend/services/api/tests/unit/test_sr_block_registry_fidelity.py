import pytest
from unittest.mock import MagicMock
from unifoli_api.services.student_record_ir_service import StudentRecordIRService
from unifoli_api.services.student_record_block_registry_service import StudentRecordBlockRegistryService

def test_sr_block_registry_fidelity_multi_page():
    """
    Ensures that a multi-page document preserves all content lines 
    as unique blocks in the registry with correct page numbers and ordering.
    """
    # 1. Setup multi-page mock
    page1 = MagicMock()
    page1.page_number = 1
    page1.width = 600
    page1.height = 800
    page1.extract_text_lines.return_value = [
        {"text": "Page 1 Line 1", "x0": 10, "top": 10, "x1": 100, "bottom": 20},
        {"text": "Page 1 Line 2", "x0": 10, "top": 30, "x1": 100, "bottom": 40}
    ]
    
    page2 = MagicMock()
    page2.page_number = 2
    page2.width = 600
    page2.height = 800
    page2.extract_text_lines.return_value = [
        {"text": "Page 2 Line 1", "x0": 10, "top": 10, "x1": 100, "bottom": 20},
        {"text": "Page 2 Line 3", "x0": 10, "top": 50, "x1": 100, "bottom": 60}
    ]
    
    mock_pages = [page1, page2]
    
    # 2. Run IR Generation
    ir_service = StudentRecordIRService()
    ir_doc = ir_service.create_ir(mock_pages)
    
    assert ir_doc.total_pages == 2
    assert len(ir_doc.pages[0].blocks) == 2
    assert len(ir_doc.pages[1].blocks) == 2
    
    # 3. Run Block Registry Building
    registry_service = StudentRecordBlockRegistryService()
    registry = registry_service.build_registry(ir_doc)
    
    # 4. Assertions on Registry Fidelity
    assert registry.total_blocks == 4
    
    # Check content preservation
    expected_texts = ["Page 1 Line 1", "Page 1 Line 2", "Page 2 Line 1", "Page 2 Line 3"]
    actual_texts = [b.text for b in registry.blocks]
    assert actual_texts == expected_texts
    
    # Check page indexing integrity
    assert registry.blocks[0].page_number == 1
    assert registry.blocks[1].page_number == 1
    assert registry.blocks[2].page_number == 2
    assert registry.blocks[3].page_number == 2
    
    # Check ordering index integrity
    assert registry.blocks[0].index == 0
    assert registry.blocks[1].index == 1
    assert registry.blocks[2].index == 2
    assert registry.blocks[3].index == 3
    
    # Check section label (should be None currently as it's not yet implemented in IR phase)
    assert registry.blocks[0].section_label is None
    
    # Check block IDs are unique and reference page
    assert registry.blocks[0].id == "blk_p1_0"
    assert registry.blocks[2].id == "blk_p2_0"

if __name__ == "__main__":
    pytest.main([__file__])
