from __future__ import annotations

import re
from datetime import datetime, timezone

from ticket_state import TicketMessage


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "u",
    "we",
    "with",
    "у",
    "в",
    "во",
    "не",
    "на",
    "и",
    "или",
    "что",
    "это",
    "как",
    "после",
    "при",
    "меня",
    "мой",
    "мне",
    "так",
    "все",
    "всё",
    "только",
}

CANONICAL_REPLACEMENTS = (
    ("личный кабинет", "personal account"),
    ("белый экран", "white screen"),
    ("после входа", "after login"),
    ("раздел отчетов", "reports section"),
    ("отчеты", "reports"),
    ("отчёты", "reports"),
    ("выгрузке", "export"),
    ("выгрузка", "export"),
    ("выгрузки", "export"),
    ("скачивается", "download"),
    ("скачанный", "download"),
    ("скачать", "download"),
    ("xlsx", "excel"),
    ("битым", "corrupt"),
    ("битый", "corrupt"),
    ("поврежден", "corrupt"),
    ("поврежденный", "corrupt"),
)

SEARCH_ALIAS_MAP = {
    "белый экран": "white screen",
    "личный кабинет": "personal account",
    "после входа": "after login",
    "не открывается": "not opening",
    "отчеты": "reports",
    "раздел отчетов": "reports section",
    "после обновления": "after update",
    "выгрузка excel": "excel export",
    "битый файл": "corrupt file",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
    for source, target in CANONICAL_REPLACEMENTS:
        lowered = lowered.replace(source, target)
    lowered = re.sub(r"[^a-zа-я0-9\s]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def tokenize(text: str) -> set[str]:
    tokens = normalize_text(text).split()
    return {token for token in tokens if len(token) > 2 and token not in STOPWORDS}


def overlap_score(query_tokens: set[str], doc_tokens: set[str], raw_query: str, doc_text: str) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0

    shared = query_tokens & doc_tokens
    jaccard = len(shared) / len(query_tokens | doc_tokens)
    phrase_bonus = 0.15 if normalize_text(raw_query) in normalize_text(doc_text) else 0.0
    keyword_bonus = min(len(shared) * 0.05, 0.25)
    return round(min(jaccard + phrase_bonus + keyword_bonus, 1.0), 4)


def get_messages_by_role(messages: list[TicketMessage], role: str) -> list[str]:
    return [item["message"] for item in messages if item["role"] == role]


def get_latest_message_by_role(messages: list[TicketMessage], role: str) -> str | None:
    for item in reversed(messages):
        if item["role"] == role:
            return item["message"]
    return None


def build_user_context(messages: list[TicketMessage]) -> str:
    return " ".join(get_messages_by_role(messages, "user")).strip()


def get_initial_user_message(messages: list[TicketMessage]) -> str:
    user_messages = get_messages_by_role(messages, "user")
    return user_messages[0] if user_messages else ""
