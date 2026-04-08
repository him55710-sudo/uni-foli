import unittest
from unittest.mock import MagicMock
from polio_api.services.student_record_pipeline_service import StudentRecordPipelineService
from polio_api.services.student_record_page_classifier_service import PageCategory

class TestStudentRecordPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = StudentRecordPipelineService()

    def test_full_pipeline_flow(self):
        # Mocking pages from pdfplumber
        mock_pages = []
        
        # Page 1: Student info
        p1 = MagicMock()
        p1.extract_text.return_value = "학교생활기록부\n성 명 : 홍길동\n생년월일 : 2006.01.01\n학교명 : 한국고등학교"
        mock_pages.append(p1)
        
        # Page 2: Attendance
        p2 = MagicMock()
        p2.extract_text.return_value = "출결상황\n1학년: 190일 출석"
        mock_pages.append(p2)
        
        # Page 3: Awards
        p3 = MagicMock()
        p3.extract_text.return_value = "수상경력\n수학경시대회 금상"
        p3.extract_tables.return_value = [[
            ["수상명", "등급", "일자", "기관", "대상"],
            ["수학경시대회", "금상", "2023.05.10", "한국고등학교", "전교생"]
        ]]
        mock_pages.append(p3)

        # Run pipeline
        raw_text = "\n".join([p.extract_text() for p in mock_pages])
        artifact = self.pipeline.process_document(mock_pages, raw_text)

        # Assertions
        self.assertIn("canonical_data", artifact)
        self.assertIn("quality_report", artifact)
        self.assertIn("chunks", artifact)
        
        canonical = artifact["canonical_data"]
        self.assertEqual(canonical["student_name"], "홍길동")
        self.assertEqual(canonical["school_name"], "한국고등학교")
        self.assertTrue(len(canonical["awards"]) > 0)
        self.assertEqual(canonical["awards"][0]["award_name"], "수학경시대회")

    def test_classification_summary(self):
        p1 = MagicMock()
        p1.extract_text.return_value = "학교생활기록부"
        
        summary = self.pipeline._get_classification_summary([
            SimpleNamespace(page_type=PageCategory.STUDENT_INFO),
            SimpleNamespace(page_type=PageCategory.BEHAVIOR),
        ])
        
        self.assertEqual(summary.get(PageCategory.STUDENT_INFO.value), 1)
        self.assertEqual(summary.get(PageCategory.BEHAVIOR.value), 1)

class SimpleNamespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

if __name__ == "__main__":
    unittest.main()
