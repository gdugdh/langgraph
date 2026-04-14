from __future__ import annotations

import os

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from models import (
    DuplicateDecision,
    IssueExample,
    IssueHandlingResult,
    IssueRecord,
    ServiceError,
)
from repo.abstractions import IssueRepository
from service.llm_factory import build_chat_llm
from service.text_utils import (
    build_user_context,
    get_initial_user_message,
    normalize_text,
    overlap_score,
    tokenize,
    utc_now,
)
from ticket_state import TicketMessage


class IssueService:
    def __init__(self, issue_repository: IssueRepository) -> ServiceError:
        self.issue_repository = issue_repository
        self.llm = build_chat_llm("SUPPORT_BOT_DEDUP_MODEL")
        if self.llm is None:
            return ServiceError(
                code="cant_connect_to_llm",
                message="Cant connect to llm. "
            )

    def handle_unresolved_ticket(
        self,
        user_id: str,
        messages: list[TicketMessage],
        category: str,
        preliminary_title: str,
    ) -> IssueHandlingResult:
        print("[IssueService] start handle_unresolved_ticket")
        issues = self.issue_repository.list_issues()
        user_context = build_user_context(messages)
        initial_message = get_initial_user_message(messages) or user_context

        issue, score = self._find_similar_issue_fast(category, messages, issues)
        is_duplicate = score >= 0.44
        if issue is not None and 0.22 <= score < 0.44:
            refinement, err = self._llm_duplicate_refinement(user_context, issue)
            if (err is None) and (refinement is not None):
                is_duplicate = refinement.is_duplicate and refinement.confidence >= 0.65

        if issue is not None and is_duplicate:
            issue.frequency += 1
            issue.last_seen_at = utc_now()
            issue.examples.append(IssueExample(user_id=user_id, message=user_context))
            issue.last_summary = user_context
            updated_issue = self.issue_repository.update_issue(issue)
            result = IssueHandlingResult(
                similar_issue_found=True,
                similar_issue_id=updated_issue.issue_id,
                created_issue_id=None,
                task_created=False,
                task_file_path=self.issue_repository.get_storage_path(),
                frequency_incremented=True,
                status="escalated_existing_issue",
                history_event="existing_issue_updated",
                similarity_score=score,
            )
            print(
                "[IssueService] end handle_unresolved_ticket "
                f"mode=existing_task issue_id={result.similar_issue_id} score={score:.4f}"
            )
            return result

        issue_title = preliminary_title.strip() or initial_message.strip()
        new_issue = IssueRecord(
            issue_id="",
            title=issue_title or "New support issue",
            normalized_problem=normalize_text(user_context),
            category=category,
            status="open",
            frequency=1,
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
            examples=[IssueExample(user_id=user_id, message=user_context)],
            last_summary=user_context,
        )
        saved_issue = self.issue_repository.save_issue(new_issue)
        result = IssueHandlingResult(
            similar_issue_found=False,
            similar_issue_id=None,
            created_issue_id=saved_issue.issue_id,
            task_created=True,
            task_file_path=self.issue_repository.get_storage_path(),
            frequency_incremented=False,
            status="escalated_new_issue",
            history_event="new_issue_created",
            similarity_score=score,
        )
        print(
            "[IssueService] end handle_unresolved_ticket "
            f"mode=new_task issue_id={result.created_issue_id} score={score:.4f}"
        )
        return result

    def _find_similar_issue_fast(
        self,
        category: str,
        messages: list[TicketMessage],
        issues: list[IssueRecord],
    ) -> tuple[IssueRecord | None, float]:
        best_issue: IssueRecord | None = None
        best_score = 0.0
        for issue in issues:
            score = self._issue_similarity(category, messages, issue)
            if score > best_score:
                best_issue = issue
                best_score = score
        return best_issue, best_score

    def _issue_similarity(
        self,
        category: str,
        messages: list[TicketMessage],
        issue: IssueRecord,
    ) -> float:
        if category != "unknown" and issue.category != category:
            return 0.0

        user_context = build_user_context(messages)
        new_tokens = tokenize(user_context)
        issue_tokens = tokenize(" ".join([issue.title, issue.normalized_problem, issue.last_summary]))
        if not new_tokens or not issue_tokens:
            return 0.0
        return overlap_score(new_tokens, issue_tokens, user_context, issue.last_summary)

    def _llm_duplicate_refinement(
        self,
        user_context: str,
        issue: IssueRecord,
    ) -> tuple[DuplicateDecision | None, ServiceError | None]:

        parser = JsonOutputParser(pydantic_object=DuplicateDecision)
        prompt = PromptTemplate(
            template=(
                "Определи, описывает ли новое обращение ту же проблему, что и существующая задача.\n"
                "Новое обращение: {request}\n"
                "Существующая задача: {issue_title}\n"
                "Сводка задачи: {issue_summary}\n"
                "{format_instructions}\n"
                "Верни только JSON."
            ),
            input_variables=["request", "issue_title", "issue_summary"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | self.llm | parser
        try:
            payload = chain.invoke(
                {
                    "request": user_context,
                    "issue_title": issue.title,
                    "issue_summary": issue.last_summary,
                }
            )
            result = DuplicateDecision.model_validate(payload)
        except Exception as exc:
            return None, ServiceError(
                code="dedup_invoke_failed",
                message=f"Dedup refinement invoke failed: {exc}",
            )

        print(
            "[IssueService] end llm_duplicate_refinement "
            f"is_duplicate={result.is_duplicate} confidence={result.confidence}"
        )
        return result, None
