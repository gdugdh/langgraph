from __future__ import annotations

from typing import Any, Literal, TypedDict


TicketStatus = Literal[
    "new",
    "need_clarification",
    "searching_kb",
    "solution_found",
    "escalated_existing_issue",
    "escalated_new_issue",
    "resolved",
    "closed",
]


class TicketMessage(TypedDict):
    role: str
    message: str


class SupportTicketState(TypedDict):
    ticket_id: str
    user_id: str
    messages: list[TicketMessage]
    preliminary_title: str
    category: str
    priority: str
    status: TicketStatus
    need_clarification: bool
    kb_results: list[dict[str, Any]]
    solution_found: bool
    solution_text: str
    similar_issue_found: bool
    similar_issue_id: str | None
    task_created: bool
    task_file_path: str | None
    frequency_incremented: bool
    final_response: str
    created_at: str
    updated_at: str
    history: list[dict[str, Any]]
