from __future__ import annotations

import math
import re
from collections import Counter
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
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


def char_wb_ngrams(text: str, ngram_range: tuple[int, int] = (2, 3)) -> list[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []

    grams: list[str] = []
    for word in cleaned.split():
        padded = f" {word} "
        for size in range(ngram_range[0], ngram_range[1] + 1):
            if len(padded) < size:
                continue
            for index in range(len(padded) - size + 1):
                grams.append(padded[index : index + size])
    return grams


def cosine_similarity(left: Counter[str] | dict[str, float], right: Counter[str] | dict[str, float]) -> float:
    if not left or not right:
        return 0.0

    if len(left) > len(right):
        left, right = right, left

    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)

class TfidfCosineSimilarity:
    name = "tfidf_char_wb_cosine"

    def fit(self, texts: list[str]) -> None:
        vectors = {text: Counter(char_wb_ngrams(text)) for text in texts}
        doc_count = len(texts)
        document_frequency: Counter[str] = Counter()
        for vector in vectors.values():
            document_frequency.update(vector.keys())

        self._vectors: dict[str, dict[str, float]] = {}
        for text, counts in vectors.items():
            tfidf: dict[str, float] = {}
            for gram, count in counts.items():
                idf = math.log((1 + doc_count) / (1 + document_frequency[gram])) + 1.0
                tfidf[gram] = count * idf
            self._vectors[text] = tfidf

    def score(self, left: str, right: str) -> float:
        return cosine_similarity(self._vectors[left], self._vectors[right])


def tfidf_cosine_score(left: str, right: str) -> float:
    similarity = TfidfCosineSimilarity()
    similarity.fit([left, right])
    return round(similarity.score(left, right), 4)


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
