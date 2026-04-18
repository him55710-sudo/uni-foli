import pytest
from unittest.mock import MagicMock
from unifoli_api.services.student_record_ir_service import StudentRecordIRService
from unifoli_api.services.student_record_block_registry_service import StudentRecordBlockRegistryService
from unifoli_api.services.student_record_judgement_service import StudentRecordJudgementService
from unifoli_api.services.student_record_link_graph_service import StudentRecordLinkGraphService

def test_judgement_categories_and_axes():
    # Mock blocks with specific keywords for testing
    mock_pages = []
    
    # Page 1: Subject Activity (세특)
    page1 = MagicMock()
    page1.page_number = 1
    page1.width = 500.0; page1.height = 700.0
    page1.extract_text_lines.return_value = [
        {"text": "수학 교과 세부능력 및 특기사항: 미분 적분을 실제 사례에 적용하여 탐구함", "x0": 10, "top": 10, "x1": 100, "bottom": 20}
    ]
    mock_pages.append(page1)
    
    # Page 2: Club Activity (동아리)
    page2 = MagicMock()
    page2.page_number = 2
    page2.width = 500.0; page2.height = 700.0
    page2.extract_text_lines.return_value = [
        {"text": "컴퓨터 동아리 활동: 파이썬을 활용한 AI 프로그램 기획", "x0": 10, "top": 10, "x1": 100, "bottom": 20}
    ]
    mock_pages.append(page2)
    
    # 1. Processing
    ir_service = StudentRecordIRService()
    ir_doc = ir_service.create_ir(mock_pages)
    
    registry_service = StudentRecordBlockRegistryService()
    registry = registry_service.build_registry(ir_doc)
    
    graph_service = StudentRecordLinkGraphService()
    graph = graph_service.build_graph(registry.blocks, [])
    
    judgement_service = StudentRecordJudgementService()
    judgements = judgement_service.generate_judgements(registry, graph)
    
    # 2. Assertions
    # We expect at least one subject judgement and one club judgement
    categories = [j.category for j in judgements]
    assert "subject_activity" in categories
    assert "club_activity" in categories
    
    # Check axes
    for j in judgements:
        assert len(j.axis_impact) > 0
        if j.category == "subject_activity":
            assert "universal_rigor" in j.axis_impact
        if j.category == "club_activity":
            assert "cluster_suitability" in j.axis_impact

if __name__ == "__main__":
    pytest.main([__file__])
