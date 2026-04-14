from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from service.text_utils import overlap_score, tokenize  # noqa: E402


ARTICLE_URL = "https://habr.com/ru/articles/923080/"


@dataclass(frozen=True)
class TextSample:
    sample_id: str
    cluster_id: str
    text: str


def article_clean_string(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^а-яa-z0-9]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def char_wb_ngrams(text: str, ngram_range: tuple[int, int] = (2, 3)) -> list[str]:
    cleaned = article_clean_string(text)
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


class OverlapSimilarity:
    name = "overlap_score"

    def fit(self, texts: list[str]) -> None:
        self._texts = texts

    def score(self, left: str, right: str) -> float:
        left_score = overlap_score(tokenize(left), tokenize(right), left, right)
        right_score = overlap_score(tokenize(right), tokenize(left), right, left)
        return (left_score + right_score) / 2


class CountCosineSimilarity:
    name = "count_char_wb_cosine"

    def fit(self, texts: list[str]) -> None:
        self._vectors = {text: Counter(char_wb_ngrams(text)) for text in texts}

    def score(self, left: str, right: str) -> float:
        return cosine_similarity(self._vectors[left], self._vectors[right])


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


class HashingCosineSimilarity:
    name = "hashing_char_wb_cosine"

    def __init__(self, buckets: int = 512) -> None:
        self.buckets = buckets

    def fit(self, texts: list[str]) -> None:
        self._vectors = {text: self._vectorize(text) for text in texts}

    def score(self, left: str, right: str) -> float:
        return cosine_similarity(self._vectors[left], self._vectors[right])

    def _vectorize(self, text: str) -> dict[str, float]:
        vector: Counter[str] = Counter()
        for gram in char_wb_ngrams(text):
            digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
            bucket = int(digest, 16) % self.buckets
            vector[str(bucket)] += 1.0
        return dict(vector)


def build_samples(seed: int = 42, variants_per_cluster: int = 12) -> list[TextSample]:
    randomizer = random.Random(seed)
    templates = [
        {
            "cluster_id": "access_white_screen",
            "phrases": [
                "После входа в личный кабинет вижу белый экран",
                "Личный кабинет открывается пустой белой страницей после авторизации",
                "После логина в ЛК экран белый и ничего не грузится",
            ],
            "details": ["в Chrome", "в веб-версии", "на версии 2.5.1", "после утреннего релиза"],
        },
        {
            "cluster_id": "access_reset_password",
            "phrases": [
                "Не приходит письмо для сброса пароля",
                "Ссылка на восстановление пароля не отправляется на почту",
                "Письмо со сбросом пароля не приходит пользователю",
            ],
            "details": ["в корпоративную почту", "у нескольких сотрудников", "с версии 3.2.0"],
        },
        {
            "cluster_id": "bug_reports_after_update",
            "phrases": [
                "После обновления не открывается раздел отчетов",
                "Раздел отчетов зависает после последнего релиза",
                "После релиза в отчетах бесконечная загрузка",
            ],
            "details": ["в браузере Chrome", "в веб-приложении", "после релиза 5.4.0"],
        },
        {
            "cluster_id": "bug_excel_export",
            "phrases": [
                "При выгрузке Excel файл скачивается поврежденным",
                "Скачанный xlsx файл битый после экспорта",
                "После выгрузки отчет в Excel не открывается",
            ],
            "details": ["в разделе отчетов", "в версии 2.8.4", "после нажатия на кнопку выгрузки"],
        },
        {
            "cluster_id": "billing_invoice_history",
            "phrases": [
                "Не могу найти историю счетов",
                "Куда делась квитанция в истории платежей",
                "В биллинге не видно старые счета",
            ],
            "details": ["за прошлый месяц", "в веб-кабинете", "на версии 1.9.0"],
        },
        {
            "cluster_id": "billing_receipt_download",
            "phrases": [
                "Не скачивается квитанция по оплате",
                "Кнопка скачивания квитанции не работает",
                "Подтверждение оплаты не скачивается из биллинга",
            ],
            "details": ["в разделе платежей", "после обновления интерфейса", "у клиента на Windows"],
        },
        {
            "cluster_id": "integration_webhook",
            "phrases": [
                "Вебхук не отправляет события в CRM",
                "События из интеграции не доходят до CRM",
                "После создания заказа webhook не срабатывает",
            ],
            "details": ["в проде", "с версии API 4.1", "для новых заказов"],
        },
        {
            "cluster_id": "integration_token",
            "phrases": [
                "После обновления перестал работать API токен",
                "Интеграция отвечает 401 после смены версии",
                "Старый токен перестал подходить к API",
            ],
            "details": ["для интеграции с ERP", "после релиза 7.0.0", "на тестовом стенде"],
        },
        {
            "cluster_id": "bug_mobile_profile_crash",
            "phrases": [
                "Мобильное приложение падает при открытии профиля",
                "После входа приложение вылетает на экране профиля",
                "При переходе в профиль мобильное приложение закрывается",
            ],
            "details": ["на Android", "на версии 6.3.2", "после обновления приложения"],
        },
        {
            "cluster_id": "access_admin_panel",
            "phrases": [
                "После смены роли пропал доступ в админку",
                "Пользователь получает access denied в панели администратора",
                "Не удается открыть административную панель после изменения прав",
            ],
            "details": ["для менеджера", "на версии 4.2.1", "сразу после смены роли"],
        },
        {
            "cluster_id": "integration_duplicate_contacts",
            "phrases": [
                "После синхронизации с CRM создаются дубли контактов",
                "Интеграция с CRM плодит повторяющиеся контакты",
                "Синхронизация дублирует контакты в CRM",
            ],
            "details": ["при ночном обмене", "для новых клиентов", "после включения интеграции"],
        },
        {
            "cluster_id": "bug_saved_filter_reset",
            "phrases": [
                "Сохраненный фильтр сбрасывается после обновления страницы",
                "После перезагрузки фильтр отчетов не сохраняется",
                "Настроенный фильтр пропадает после refresh",
            ],
            "details": ["в разделе отчетов", "в веб-версии", "на версии 3.4.7"],
        },
    ]

    samples: list[TextSample] = []
    for template in templates:
        for variant_index in range(variants_per_cluster):
            text = mutate_issue_text(
                randomizer=randomizer,
                phrase=randomizer.choice(template["phrases"]),
                details=template["details"],
                variant_index=variant_index,
            )
            samples.append(
                TextSample(
                    sample_id=f"{template['cluster_id']}_{variant_index}",
                    cluster_id=template["cluster_id"],
                    text=text,
                )
            )
    return samples


def mutate_issue_text(
    randomizer: random.Random,
    phrase: str,
    details: list[str],
    variant_index: int,
) -> str:
    text = phrase

    replacements = [
        ("личный кабинет", randomizer.choice(["личный кабинет", "кабинет", "ЛК"])),
        ("после входа", randomizer.choice(["после входа", "сразу после входа", "после авторизации"])),
        ("не открывается", randomizer.choice(["не открывается", "не загружается", "не грузится"])),
        ("обновления", randomizer.choice(["обновления", "релиза", "деплоя"])),
        ("поврежденным", randomizer.choice(["поврежденным", "битым", "испорченным"])),
        ("квитанция", randomizer.choice(["квитанция", "чек", "подтверждение оплаты"])),
        ("интеграция", randomizer.choice(["интеграция", "синхронизация", "обмен"])),
    ]
    for source, target in replacements:
        text = text.replace(source, target)

    selected_details = randomizer.sample(details, k=randomizer.randint(1, min(2, len(details))))
    if selected_details:
        text = f"{text}. {' '.join(selected_details)}"

    if variant_index % 3 == 0:
        text = f"Проблема: {text}"
    elif variant_index % 3 == 1:
        text = f"{text} Помогите разобраться."

    if variant_index % 4 == 0:
        text = inject_typo(randomizer, text)

    if variant_index % 5 == 0:
        text = text.replace(" и ", " & ")

    if variant_index % 6 == 0:
        text = text.upper()

    return text


def inject_typo(randomizer: random.Random, text: str) -> str:
    words = text.split()
    if not words:
        return text

    index = randomizer.randrange(len(words))
    word = words[index]
    if len(word) < 4:
        return text

    mode = randomizer.choice(["swap", "drop", "repeat"])
    if mode == "swap" and len(word) >= 5:
        char_index = randomizer.randrange(1, len(word) - 2)
        chars = list(word)
        chars[char_index], chars[char_index + 1] = chars[char_index + 1], chars[char_index]
        words[index] = "".join(chars)
    elif mode == "drop":
        char_index = randomizer.randrange(1, len(word) - 1)
        words[index] = word[:char_index] + word[char_index + 1 :]
    else:
        char_index = randomizer.randrange(1, len(word) - 1)
        words[index] = word[:char_index] + word[char_index] + word[char_index:]
    return " ".join(words)


def evaluate_algorithms(samples: list[TextSample]) -> dict[str, dict[str, float]]:
    texts = [sample.text for sample in samples]
    algorithms = [
        OverlapSimilarity(),
        CountCosineSimilarity(),
        TfidfCosineSimilarity(),
        HashingCosineSimilarity(),
    ]

    results: dict[str, dict[str, float]] = {}
    for algorithm in algorithms:
        algorithm.fit(texts)
        pair_scores: list[tuple[float, bool]] = []
        top1_hits = 0
        top3_hits = 0

        for index, sample in enumerate(samples):
            rankings: list[tuple[float, bool]] = []
            for candidate_index, candidate in enumerate(samples):
                if index == candidate_index:
                    continue
                score = algorithm.score(sample.text, candidate.text)
                is_duplicate = sample.cluster_id == candidate.cluster_id
                pair_scores.append((score, is_duplicate))
                rankings.append((score, is_duplicate))

            rankings.sort(key=lambda item: item[0], reverse=True)
            if rankings and rankings[0][1]:
                top1_hits += 1
            if any(item[1] for item in rankings[:3]):
                top3_hits += 1

        best_f1, best_threshold, best_precision, best_recall = compute_best_f1(pair_scores)
        results[algorithm.name] = {
            "top1_accuracy": round(top1_hits / len(samples), 4),
            "recall_at_3": round(top3_hits / len(samples), 4),
            "best_f1": round(best_f1, 4),
            "best_precision": round(best_precision, 4),
            "best_recall": round(best_recall, 4),
            "best_threshold": round(best_threshold, 4),
            "samples": float(len(samples)),
        }
    return results


def compute_best_f1(pair_scores: list[tuple[float, bool]]) -> tuple[float, float, float, float]:
    best_f1 = 0.0
    best_threshold = 0.0
    best_precision = 0.0
    best_recall = 0.0
    thresholds = sorted({score for score, _ in pair_scores}, reverse=True)
    positive_total = sum(1 for _, is_positive in pair_scores if is_positive)

    for threshold in thresholds:
        true_positive = 0
        false_positive = 0
        for score, is_positive in pair_scores:
            if score >= threshold:
                if is_positive:
                    true_positive += 1
                else:
                    false_positive += 1
        false_negative = positive_total - true_positive
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
        recall = true_positive / positive_total if positive_total else 0.0
        if precision + recall == 0.0:
            continue
        f1 = 2 * precision * recall / (precision + recall)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
            best_precision = precision
            best_recall = recall

    return best_f1, best_threshold, best_precision, best_recall
