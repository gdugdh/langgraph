from __future__ import annotations

import json
from pathlib import Path

from repo.abstractions import TaxonomyRepository


class FileTaxonomyRepository(TaxonomyRepository):
    def __init__(self, path: Path) -> None:
        self.path = path

    def list_categories(self) -> list[str]:
        payload = self._load_payload()
        return payload.get("categories", [])

    def list_priorities(self) -> list[str]:
        payload = self._load_payload()
        return payload.get("priorities", [])

    def _load_payload(self) -> dict:
        if not self.path.exists():
            return {"categories": [], "priorities": []}
        return json.loads(self.path.read_text(encoding="utf-8"))
