from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from repo.file_issue_repository import FileIssueRepository
from repo.file_kb_repository import FileKnowledgeBaseRepository
from repo.file_taxonomy_repository import FileTaxonomyRepository
from service.issue_service import IssueService
from service.kb_search_service import KnowledgeBaseSearchService
from service.ticket_classifier_service import TicketClassifierService
from service.text_utils import get_latest_message_by_role, utc_now
from ticket_state import SupportTicketState, TicketStatus
from config.llm_factory import build_chat_llm


BASE_DIR = Path(__file__).resolve().parent
KB_DIR = Path(os.getenv("SUPPORT_BOT_KB_DIR", str(BASE_DIR / "kb"))).resolve()
ISSUES_PATH = Path(os.getenv("SUPPORT_BOT_ISSUES_PATH", str(BASE_DIR / "issues.json"))).resolve()
TAXONOMY_PATH = Path(
    os.getenv("SUPPORT_BOT_TAXONOMY_PATH", str(BASE_DIR / "data" / "taxonomy.json"))
).resolve()


def append_history(
    state: SupportTicketState,
    node: str,
    event: str,
    **details: Any,
) -> list[dict[str, Any]]:
    return state["history"] + [{"at": utc_now(), "node": node, "event": event, "details": details}]


def get_created_issue_id(state: SupportTicketState) -> str | None:
    for item in reversed(state["history"]):
        if item["node"] == "manage_issue" and item["event"] == "new_issue_created":
            return item["details"].get("created_issue_id")
    return None


def receive_ticket_node(state: SupportTicketState) -> dict[str, Any]:
    user_id = state["user_id"].strip() or "demo-user"
    if not state["messages"]:
        raise RuntimeError("Ticket message is empty.")
    message = state["messages"][0]["message"].strip()
    if not message:
        raise RuntimeError("Ticket message is empty.")
    now = utc_now()
    return {
        "ticket_id": str(uuid.uuid4()),
        "user_id": user_id,
        "messages": [{"role": "user", "message": message}],
        "status": "new",
        "created_at": now,
        "updated_at": now,
        "history": append_history(
            state,
            "receive_ticket",
            "ticket_received",
            user_id=user_id,
        ),
    }


def classify_ticket_node(
    state: SupportTicketState,
    classifier_service: TicketClassifierService,
) -> dict[str, Any]:
    classification, error = classifier_service.classify(state["messages"])
    if error is not None or classification is None:
        raise RuntimeError(
            error.message if error is not None else "Classifier failed without returning a result."
        )

    question = classification.question.strip()
    asked_questions = [item["message"] for item in state["messages"] if item["role"] == "assistant"]
    can_ask_more = len(asked_questions) < 3
    should_clarify = classification.need_clarification and bool(question) and can_ask_more
    updated_messages = list(state["messages"])

    # Вопрос добавляем в messages здесь, чтобы clarify_ticket читал ровно последний вопрос.
    if should_clarify and question not in asked_questions:
        updated_messages.append({"role": "assistant", "message": question})
    elif question in asked_questions:
        should_clarify = False
        question = ""

    next_status: TicketStatus = "need_clarification" if should_clarify else "searching_kb"
    return {
        "preliminary_title": classification.preliminary_title.strip(),
        "category": classification.category,
        "priority": classification.priority,
        "need_clarification": should_clarify,
        "messages": updated_messages,
        "status": next_status,
        "updated_at": utc_now(),
        "history": append_history(
            state,
            "classify_ticket",
            "classified",
            preliminary_title=classification.preliminary_title,
            category=classification.category,
            priority=classification.priority,
            need_clarification=should_clarify,
            clarification_attempts=len(asked_questions),
            question=question,
            reasoning=classification.reasoning,
        ),
    }


def clarify_ticket_node(state: SupportTicketState) -> dict[str, Any]:
    question = get_latest_message_by_role(state["messages"], "assistant")
    if not question:
        return {
            "need_clarification": False,
            "status": "searching_kb",
            "updated_at": utc_now(),
            "history": append_history(
                state,
                "clarify_ticket",
                "clarification_skipped",
                reason="missing_question",
            ),
        }

    answer = input(f"Уточнение: {question} ").strip()
    updated_messages = list(state["messages"]) + [{"role": "user", "message": answer}]
    return {
        "messages": updated_messages,
        "status": "new",
        "updated_at": utc_now(),
        "history": append_history(
            state,
            "clarify_ticket",
            "clarification_received",
            question=question,
        ),
    }


def search_kb_node(
    state: SupportTicketState,
    search_service: KnowledgeBaseSearchService,
) -> dict[str, Any]:
    result = search_service.search_ticket(messages=state["messages"], category=state["category"])
    return {
        "kb_results": result.kb_results,
        "solution_found": result.solution_found,
        "solution_text": result.solution_text,
        "status": "solution_found" if result.solution_found else "searching_kb",
        "updated_at": utc_now(),
        "history": append_history(
            state,
            "search_kb",
            "kb_searched",
            queries=result.search_queries,
            hits=result.kb_results,
            solution_found=result.solution_found,
        ),
    }


def manage_issue_node(state: SupportTicketState, issue_service: IssueService) -> dict[str, Any]:
    result = issue_service.handle_unresolved_ticket(
        user_id=state["user_id"],
        messages=state["messages"],
        category=state["category"],
        preliminary_title=state["preliminary_title"],
    )
    return {
        "similar_issue_found": result.similar_issue_found,
        "similar_issue_id": result.similar_issue_id,
        "task_created": result.task_created,
        "task_file_path": result.task_file_path,
        "frequency_incremented": result.frequency_incremented,
        "status": result.status,
        "updated_at": utc_now(),
        "history": append_history(
            state,
            "manage_issue",
            result.history_event,
            similar_issue_id=result.similar_issue_id,
            created_issue_id=result.created_issue_id,
            similarity_score=result.similarity_score,
        ),
    }


def finalize_response_node(state: SupportTicketState) -> dict[str, Any]:
    created_issue_id = get_created_issue_id(state)

    if state["solution_found"]:
        response = (
            f"Тикет {state['ticket_id']}\n"
            f"Категория: {state['category']}\n"
            f"Приоритет: {state['priority']}\n\n"
            f"{state['solution_text']}\n"
            "Если решение не поможет, обращение будет эскалировано при следующем запуске."
        )
        final_status: TicketStatus = "resolved"
    elif state["similar_issue_found"] and state["similar_issue_id"]:
        response = (
            f"Тикет {state['ticket_id']}\n"
            "Надёжного решения в базе знаний не найдено.\n"
            f"Похожая проблема уже зарегистрирована: {state['similar_issue_id']}.\n"
            "Ваше обращение добавлено в существующую задачу, частота проблемы увеличена."
        )
        final_status = "closed"
    else:
        response = (
            f"Тикет {state['ticket_id']}\n"
            "Надёжного решения в базе знаний не найдено, совпадений среди задач тоже нет.\n"
            f"Создана новая задача: {created_issue_id or 'UNKNOWN-ISSUE'}.\n"
            f"Файл реестра: {state['task_file_path']}"
        )
        final_status = "closed"

    print("\n--- Финальный ответ ---")
    print(response)

    return {
        "final_response": response,
        "messages": list(state["messages"]) + [{"role": "assistant", "message": response}],
        "status": final_status,
        "updated_at": utc_now(),
        "history": append_history(
            state,
            "finalize_response",
            "response_sent",
            solution_found=state["solution_found"],
            similar_issue_found=state["similar_issue_found"],
            final_status=final_status,
        ),
    }


def route_after_classification(state: SupportTicketState) -> str:
    return "clarify_ticket" if state["need_clarification"] else "search_kb"


def route_after_search(state: SupportTicketState) -> str:
    return "finalize_response" if state["solution_found"] else "manage_issue"


def build_graph(
    classifier_service: TicketClassifierService,
    search_service: KnowledgeBaseSearchService,
    issue_service: IssueService,
):
    graph = StateGraph(SupportTicketState)
    graph.add_node("receive_ticket", receive_ticket_node)
    graph.add_node("classify_ticket", lambda state: classify_ticket_node(state, classifier_service))
    graph.add_node("clarify_ticket", clarify_ticket_node)
    graph.add_node("search_kb", lambda state: search_kb_node(state, search_service))
    graph.add_node("manage_issue", lambda state: manage_issue_node(state, issue_service))
    graph.add_node("finalize_response", finalize_response_node)

    graph.add_edge(START, "receive_ticket")
    graph.add_edge("receive_ticket", "classify_ticket")
    graph.add_conditional_edges(
        "classify_ticket",
        route_after_classification,
        {
            "clarify_ticket": "clarify_ticket",
            "search_kb": "search_kb",
        },
    )
    graph.add_edge("clarify_ticket", "classify_ticket")
    graph.add_conditional_edges(
        "search_kb",
        route_after_search,
        {
            "finalize_response": "finalize_response",
            "manage_issue": "manage_issue",
        },
    )
    graph.add_edge("manage_issue", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()


def initial_state(user_id: str = "", initial_message: str = "") -> SupportTicketState:
    now = utc_now()
    return {
        "ticket_id": "",
        "user_id": user_id,
        "messages": [{"role": "user", "message": initial_message}] if initial_message else [],
        "preliminary_title": "",
        "category": "unknown",
        "priority": "medium",
        "status": "new",
        "need_clarification": False,
        "kb_results": [],
        "solution_found": False,
        "solution_text": "",
        "similar_issue_found": False,
        "similar_issue_id": None,
        "task_created": False,
        "task_file_path": None,
        "frequency_incremented": False,
        "final_response": "",
        "created_at": now,
        "updated_at": now,
        "history": [],
    }


def build_app():
    taxonomy_repo = FileTaxonomyRepository(TAXONOMY_PATH)
    issue_repo = FileIssueRepository(ISSUES_PATH)
    kb_repo = FileKnowledgeBaseRepository(KB_DIR)

    classifier_llm, _classifier_error = build_chat_llm("SUPPORT_BOT_CLASSIFIER_MODEL")
    dedup_llm, _dedup_error = build_chat_llm("SUPPORT_BOT_DEDUP_MODEL")

    classifier_service = TicketClassifierService(taxonomy_repo, classifier_llm)
    search_service = KnowledgeBaseSearchService(kb_repo)
    issue_service = IssueService(issue_repo, dedup_llm)

    return build_graph(
        classifier_service=classifier_service,
        search_service=search_service,
        issue_service=issue_service,
    )


def main() -> None:
    print("Support Bot MVP")
    print("Flow: intake -> classify -> clarify(if needed, up to 3 times) -> search KB -> issue handling -> final response")
    print(f"KB directory: {KB_DIR}")
    print(f"Issue registry: {ISSUES_PATH}")
    print(f"Taxonomy file: {TAXONOMY_PATH}")

    app = build_app()
    user_id = input("ID пользователя [demo-user]: ").strip() or "demo-user"
    print("Введите проблему. Команды выхода: exit, quit, выход")

    while True:
        problem = input("\nОпишите проблему: ").strip()
        if problem.lower() in {"exit", "quit", "выход"}:
            print("Завершение работы.")
            break
        if not problem:
            print("Пустой ввод пропущен.")
            continue

        try:
            final_state = app.invoke(initial_state(user_id=user_id, initial_message=problem))
        except RuntimeError as exc:
            print(f"\nExecution failed: {exc}")
            continue

        print("\n--- Сводка по тикету ---")
        print(
            json.dumps(
                {
                    "ticket_id": final_state["ticket_id"],
                    "user_id": final_state["user_id"],
                    "messages": final_state["messages"],
                    "preliminary_title": final_state["preliminary_title"],
                    "category": final_state["category"],
                    "priority": final_state["priority"],
                    "status": final_state["status"],
                    "need_clarification": final_state["need_clarification"],
                    "kb_results": final_state["kb_results"],
                    "solution_found": final_state["solution_found"],
                    "solution_text": final_state["solution_text"],
                    "similar_issue_found": final_state["similar_issue_found"],
                    "similar_issue_id": final_state["similar_issue_id"],
                    "task_created": final_state["task_created"],
                    "task_file_path": final_state["task_file_path"],
                    "frequency_incremented": final_state["frequency_incremented"],
                    "final_response": final_state["final_response"],
                    "created_at": final_state["created_at"],
                    "updated_at": final_state["updated_at"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
