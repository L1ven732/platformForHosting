"""Фильтр запрещённых слов."""

import logging
import re
from html import unescape


logger = logging.getLogger(__name__)


BANNED_WORDS = [
    "очень_сложный_тестовый_банворд",
    "ещё_один_банворд"
]


def strip_html(text: str) -> str:
    """Удаляет HTML-теги и декодирует сущности."""

    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def normalize_text(text: str) -> str:
    """Нормализует текст для проверки на бан-слова."""

    text = strip_html(text)
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_to_pattern(word: str) -> str:
    """Преобразует слово в regex-паттерн для гибкого поиска."""

    letters = list(word.lower().replace("ё", "е"))
    return r"[\W_]*".join(map(re.escape, letters))


def find_banned_words(text: str):
    """Возвращает найденные запрещённые слова в тексте."""

    normalized = normalize_text(text)
    found = []

    for word in BANNED_WORDS:
        pattern = word_to_pattern(word)
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            found.append(word)

    unique_found = sorted(set(found))
    if unique_found:
        logger.debug("Profanity detected words=%s", unique_found)
    else:
        logger.debug("Profanity check passed")
    return unique_found


def contains_profanity(text: str) -> bool:
    """Признак наличия запрещённых слов."""

    result = bool(find_banned_words(text))
    logger.debug("contains_profanity=%s", result)
    return result
