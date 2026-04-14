from __future__ import annotations

from pathlib import Path

from models import KnowledgeBaseDocument
from repo.abstractions import KnowledgeBaseRepository


class FileKnowledgeBaseRepository(KnowledgeBaseRepository):
    def __init__(self, kb_dir: Path) -> None:
        self.kb_dir = kb_dir

    def list_documents(self) -> list[KnowledgeBaseDocument]:
        documents: list[KnowledgeBaseDocument] = []
        for path in sorted(self.kb_dir.rglob("*.md")):
            content = path.read_text(encoding="utf-8")
            documents.append(
                KnowledgeBaseDocument(
                    path=str(path.relative_to(self.kb_dir.parent)),
                    title=self._extract_title(content, path.stem.replace("_", " ").title()),
                    content=content,
                )
            )
        return documents

    @staticmethod
    def _extract_title(content: str, default: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return default
