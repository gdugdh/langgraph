from __future__ import annotations

from abc import ABC, abstractmethod

from models import IssueRecord, KnowledgeBaseDocument


class TaxonomyRepository(ABC):
    @abstractmethod
    def list_categories(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def list_priorities(self) -> list[str]:
        raise NotImplementedError


class IssueRepository(ABC):
    @abstractmethod
    def list_issues(self) -> list[IssueRecord]:
        raise NotImplementedError

    @abstractmethod
    def save_issue(self, issue: IssueRecord) -> IssueRecord:
        raise NotImplementedError

    @abstractmethod
    def update_issue(self, issue: IssueRecord) -> IssueRecord:
        raise NotImplementedError

    @abstractmethod
    def get_storage_path(self) -> str:
        raise NotImplementedError


class KnowledgeBaseRepository(ABC):
    @abstractmethod
    def list_documents(self) -> list[KnowledgeBaseDocument]:
        raise NotImplementedError
