from __future__ import annotations

import json

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from models import ServiceError, TicketClassification
from repo.abstractions import TaxonomyRepository
from service.llm_factory import build_chat_llm
from ticket_state import TicketMessage



class TicketClassifierService:
    def __init__(self, taxonomy_repo: TaxonomyRepository) -> ServiceError | None:
        self.taxonomy_repo = taxonomy_repo
        self.llm = build_chat_llm("SUPPORT_BOT_CLASSIFIER_MODEL")
        if self.llm is None:
            return ServiceError(
                code="cant_connect_to_llm",
                message="Cant connect to llm. "
            )

    def classify(
        self,
        messages: list[TicketMessage],
    ) -> tuple[TicketClassification | None, ServiceError | None]:
        print("[TicketClassifierService] start classify")
        categories = self.taxonomy_repo.list_categories()
        priorities = self.taxonomy_repo.list_priorities()

        if self.llm is None:
            return None, ServiceError(
                code="classifier_llm_not_configured",
                message=(
                    "Classifier LLM is not configured. "
                    "Set `SUPPORT_BOT_CLASSIFIER_MODEL` and provider credentials."
                ),
            )

        parser = JsonOutputParser(pydantic_object=TicketClassification)
        prompt = PromptTemplate(
            template=(
                "Ты администратор первой линии корпоративной техподдержки.\n"
                "Тебе приходит заявка в виде диалога между пользователем и поддержкой.\n"
                "Сформируй краткий preliminary_title, определи категорию обращения, приоритет "
                "и нужно ли задавать следующий уточняющий вопрос.\n"
                "Категории: {categories}.\n"
                "Приоритеты: {priorities}.\n"
                "Считай, что проблема описана достаточно полно и новые вопросы не нужны, когда понятны:\n"
                "- где именно возникает проблема\n"
                "- когда она возникает или как её воспроизвести\n"
                "- версия приложения, клиента или окружения, если это влияет на диагностику\n"
                "Если этой информации уже достаточно, дополнительных вопросов не задавай.\n"
                "Если данных не хватает, верни один следующий самый полезный вопрос.\n"
                "Если вопрос не нужен, верни пустую строку в поле question.\n"
                "Диалог по заявке: {messages}\n"
                "{format_instructions}\n"
                "Верни только JSON."
            ),
            input_variables=["categories", "priorities", "messages"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | self.llm | parser

        try:
            payload = chain.invoke(
                {
                    "categories": ", ".join(categories),
                    "priorities": ", ".join(priorities),
                    "messages": json.dumps(messages, ensure_ascii=False),
                }
            )
            result = TicketClassification.model_validate(payload)
        except Exception as exc:
            return None, ServiceError(
                code="classifier_invoke_failed",
                message=f"Classifier invoke failed: {exc}",
            )

        if result.category not in categories:
            return None, ServiceError(
                code="classifier_invalid_category",
                message=f"Classifier returned unsupported category: {result.category}",
            )
        if result.priority not in priorities:
            return None, ServiceError(
                code="classifier_invalid_priority",
                message=f"Classifier returned unsupported priority: {result.priority}",
            )
        if not result.preliminary_title.strip():
            return None, ServiceError(
                code="classifier_missing_title",
                message="Classifier returned empty preliminary_title.",
            )
        if result.need_clarification and not result.question.strip():
            return None, ServiceError(
                code="classifier_missing_question",
                message="Classifier marked clarification required but returned an empty question.",
            )

        if not result.need_clarification:
            result.question = ""

        print(
            "[TicketClassifierService] end classify "
            f"title={result.preliminary_title!r} "
            f"category={result.category} priority={result.priority} "
            f"need_clarification={result.need_clarification}"
        )
        return result, None
