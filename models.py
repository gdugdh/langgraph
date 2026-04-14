from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from ticket_state import TicketStatus


class TicketClassification(BaseModel):
    preliminary_title: str = Field(description="Preliminary title of the ticket")
    category: str = Field(description="Support ticket category")
    priority: str = Field(description="Support ticket priority")
    need_clarification: bool = Field(
        description="Whether additional details are needed before KB search"
    )
    question: str = Field(
        description="Single next clarifying question, or empty string when no clarification is needed",
        max_length=200,
    )
    reasoning: str = Field(description="Short explanation of the decision", max_length=200)


@dataclass
class ServiceError:
    code: str
    message: str

class DuplicateDecision(BaseModel):
    is_duplicate: bool = Field(description="True if the issue matches an existing issue")
    confidence: float = Field(description="Decision confidence", ge=0.0, le=1.0)
    reasoning: str = Field(description="Short explanation", max_length=160)


class IssueExample(BaseModel):
    user_id: str
    message: str


class IssueRecord(BaseModel):
    issue_id: str
    title: str
    normalized_problem: str
    category: str
    status: str
    frequency: int
    first_seen_at: str
    last_seen_at: str
    examples: list[IssueExample]
    last_summary: str


class KnowledgeBaseSearchResult(BaseModel):
    search_queries: list[str]
    kb_results: list[dict[str, Any]]
    solution_found: bool
    solution_text: str


class IssueHandlingResult(BaseModel):
    similar_issue_found: bool
    similar_issue_id: str | None
    created_issue_id: str | None
    task_created: bool
    task_file_path: str
    frequency_incremented: bool
    status: TicketStatus
    history_event: str
    similarity_score: float


@dataclass
class KnowledgeBaseDocument:
    path: str
    title: str
    content: str


@dataclass
class SearchHit:
    path: str
    title: str
    score: float
    snippet: str
    query: str
    resolution: list[str]
    matched_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "score": round(self.score, 4),
            "snippet": self.snippet,
            "query": self.query,
            "resolution": self.resolution,
            "matched_terms": self.matched_terms,
        }
