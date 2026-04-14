from __future__ import annotations

import json
import re
from pathlib import Path

from models import IssueRecord
from repo.abstractions import IssueRepository


class FileIssueRepository(IssueRepository):
    def __init__(self, path: Path) -> None:
        self.path = path

    def list_issues(self) -> list[IssueRecord]:
        if not self.path.exists():
            return []
        content = self.path.read_text(encoding="utf-8").strip()
        payload = json.loads(content or "[]")
        return [IssueRecord.model_validate(item) for item in payload]

    def save_issue(self, issue: IssueRecord) -> IssueRecord:
        issues = self.list_issues()
        saved_issue = issue.model_copy(deep=True)
        if not saved_issue.issue_id:
            saved_issue.issue_id = self._next_issue_id(issues)
        issues.append(saved_issue)
        self._write_issues(issues)
        return saved_issue

    def update_issue(self, issue: IssueRecord) -> IssueRecord:
        issues = self.list_issues()
        for index, existing_issue in enumerate(issues):
            if existing_issue.issue_id == issue.issue_id:
                updated_issue = issue.model_copy(deep=True)
                issues[index] = updated_issue
                self._write_issues(issues)
                return updated_issue
        raise ValueError(f"Issue not found for update: {issue.issue_id}")

    def get_storage_path(self) -> str:
        return str(self.path)

    def _write_issues(self, issues: list[IssueRecord]) -> None:
        serialized = [issue.model_dump(mode="json") for issue in issues]
        self.path.write_text(
            json.dumps(serialized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _next_issue_id(issues: list[IssueRecord]) -> str:
        numeric: list[int] = []
        for issue in issues:
            match = re.match(r"ISSUE-(\d+)$", issue.issue_id)
            if match:
                numeric.append(int(match.group(1)))
        return f"ISSUE-{max(numeric, default=1000) + 1}"
