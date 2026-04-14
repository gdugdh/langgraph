from __future__ import annotations

import re

from models import KnowledgeBaseSearchResult, SearchHit
from repo.abstractions import KnowledgeBaseRepository
from service.text_utils import (
    build_user_context,
    normalize_text,
    tfidf_cosine_score,
    tokenize,
)
from ticket_state import TicketMessage


class KnowledgeBaseSearchService:
    def __init__(self, kb_repository: KnowledgeBaseRepository) -> None:
        self.kb_repository = kb_repository

    def search_ticket(self, messages: list[TicketMessage], category: str) -> KnowledgeBaseSearchResult:
        # print("[KnowledgeBaseSearchService] start search_ticket")
        queries = self._build_search_queries(messages, category)
        hits = self._search(queries)
        solution_found = bool(hits and hits[0].score >= 0.22 and len(hits[0].matched_terms) >= 2)
        solution_text = ""

        if solution_found:
            best_hit = hits[0]
            steps = best_hit.resolution or [best_hit.snippet]
            rendered_steps = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
            solution_text = (
                f"В базе знаний найдено вероятное решение: {best_hit.title}\n"
                f"Источник: {best_hit.path}\n"
                f"{rendered_steps}"
            )

        result = KnowledgeBaseSearchResult(
            search_queries=queries,
            kb_results=[hit.to_dict() for hit in hits],
            solution_found=solution_found,
            solution_text=solution_text,
        )
        # print(
        #     "[KnowledgeBaseSearchService] end search_ticket "
        #     f"queries={len(result.search_queries)} hits={len(result.kb_results)} "
        #     f"solution_found={result.solution_found}"
        # )
        return result

    def _search(self, queries: list[str]) -> list[SearchHit]:
        # print(f"[KnowledgeBaseSearchService] start search queries={len(queries)}")
        all_hits: dict[str, SearchHit] = {}
        documents = self.kb_repository.list_documents()
        for query in queries:
            query_tokens = tokenize(query)
            if not query_tokens:
                continue

            for document in documents:
                doc_tokens = tokenize(document.content)
                score = tfidf_cosine_score(query, document.content)
                if score <= 0:
                    continue

                hit = SearchHit(
                    path=document.path,
                    title=document.title,
                    score=score,
                    snippet=self._extract_snippet(document.content, query_tokens),
                    query=query,
                    resolution=self._extract_resolution_steps(document.content),
                    matched_terms=sorted(query_tokens & doc_tokens),
                )
                existing = all_hits.get(document.path)
                if existing is None or hit.score > existing.score:
                    all_hits[document.path] = hit
        result = sorted(all_hits.values(), key=lambda item: item.score, reverse=True)[:5]
        # print(f"[KnowledgeBaseSearchService] end search hits={len(result)}")
        return result

    def _build_search_queries(self, messages: list[TicketMessage], category: str) -> list[str]:
        # print("[KnowledgeBaseSearchService] start build_search_queries")
        merged_context = build_user_context(messages)
        base = [merged_context]
        normalized = normalize_text(merged_context)
        if normalized:
            base.append(normalized)

        if category == "access" and any(
            hint in normalized for hint in {"белый экран", "после входа", "личный кабинет", "кабинет"}
        ):
            base.append("белый экран после входа в личный кабинет")
            base.append("личный кабинет белый экран после входа кэш браузера")
        elif category == "bug" and any(
            hint in normalized for hint in {"excel", "xlsx", "выгруз", "скач", "поврежден", "бит"}
        ):
            base.append("выгрузка excel поврежденный файл")
            base.append("скачанный файл поврежден после выгрузки")
        elif category == "bug" and any(
            hint in normalized for hint in {"отчет", "отчетов", "обновлен", "релиз", "спиннер"}
        ):
            base.append("раздел отчетов не открывается после обновления")
            base.append("после обновления пустой экран в отчетах")
        elif category == "billing" and any(
            hint in normalized for hint in {"счет", "счетов", "квитанц", "платеж", "биллинг"}
        ):
            base.append("история счетов и платежных документов")
            base.append("не могу найти квитанцию или счет")
        elif category == "integration" and any(
            hint in normalized for hint in {"api", "webhook", "вебхук", "интеграц", "синхрон"}
        ):
            base.append("ошибка интеграции api webhook синхронизация")
            base.append("не приходит событие из интеграции")

        unique_queries: list[str] = []
        seen: set[str] = set()
        for query in base:
            cleaned = query.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique_queries.append(cleaned)
        result = unique_queries[:5]
        # print(f"[KnowledgeBaseSearchService] end build_search_queries queries={len(result)}")
        return result

    @staticmethod
    def _extract_snippet(text: str, query_tokens: set[str], max_len: int = 220) -> str:
        for line in text.splitlines():
            if query_tokens & tokenize(line):
                return line.strip()[:max_len]
        compact = " ".join(part.strip() for part in text.splitlines() if part.strip())
        return compact[:max_len]

    @staticmethod
    def _extract_resolution_steps(text: str) -> list[str]:
        lines = text.splitlines()
        in_resolution = False
        steps: list[str] = []
        for line in lines:
            section = line.strip().lower()
            if section in {"## resolution", "## решение"}:
                in_resolution = True
                continue
            if in_resolution and line.startswith("## "):
                break
            if in_resolution and line.strip().startswith(("-", "*")):
                steps.append(line.strip().lstrip("-* ").strip())
            if in_resolution and re.match(r"^\d+\.\s", line.strip()):
                steps.append(re.sub(r"^\d+\.\s*", "", line.strip()))
        return steps
