import pytest
from unittest.mock import MagicMock
from unifoli_api.services.diagnosis_runtime_service import _extract_document_text

def test_extract_document_text_prioritizes_block_registry():
    # Mock document with block registry in metadata
    document = MagicMock()
    document.content_text = ""
    document.content_markdown = ""
    
    metadata = {
        "analysis_artifact": {
            "sr_full_fidelity": {
                "block_registry": {
                    "blocks": [
                        {"text": "Block 1 Content"},
                        {"text": "Block 2 Content"}
                    ]
                }
            }
        },
        "student_record_canonical": {
            "timeline_signals": [{"signal": "Legacy Signal"}]
        }
    }
    document.parse_metadata = metadata
    
    text = _extract_document_text(document)
    
    # Assert that it used the block registry (Priority 1)
    assert "Block 1 Content" in text
    assert "Block 2 Content" in text
    assert "Legacy Signal" not in text # Should not reach priority 2

def test_extract_document_text_fallbacks():
    # Mock document without block registry
    document = MagicMock()
    document.content_text = ""
    document.content_markdown = ""
    
    metadata = {
        "student_record_canonical": {
            "timeline_signals": [{"signal": "Target Signal"}]
        }
    }
    document.parse_metadata = metadata
    
    text = _extract_document_text(document)
    
    # Assert that it used the canonical metadata (Priority 2)
    assert "Target Signal" in text

if __name__ == "__main__":
    pytest.main([__file__])
