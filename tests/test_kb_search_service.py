from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from models import KnowledgeBaseDocument  # noqa: E402
from service.kb_search_service import KnowledgeBaseSearchService  # noqa: E402


class DummyKnowledgeBaseRepository:
    def list_documents(self) -> list[KnowledgeBaseDocument]:
        return []


class KnowledgeBaseSearchServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = KnowledgeBaseSearchService(DummyKnowledgeBaseRepository())

    def test_access_queries_are_russian(self) -> None:
        queries = self.service._build_search_queries(
            messages=[
                {"role": "user", "message": "После входа в личный кабинет вижу белый экран в Chrome"}
            ],
            category="access",
        )
        self.assertTrue(any("белый экран" in query for query in queries))
        self.assertFalse(any("white screen after login" in query for query in queries))

    def test_bug_export_queries_are_russian(self) -> None:
        queries = self.service._build_search_queries(
            messages=[
                {"role": "user", "message": "При выгрузке Excel файл скачивается поврежденным"}
            ],
            category="bug",
        )
        self.assertTrue(any("выгрузка excel" in query for query in queries))
        self.assertTrue(any("поврежден" in query or "бит" in query for query in queries))
        self.assertFalse(any("corrupted file" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
