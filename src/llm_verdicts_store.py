from __future__ import annotations

import json
import logging
from pathlib import Path

from src.storage import atomic_write_json

logger = logging.getLogger(__name__)

_STORE_PATH = Path("data/llm_verdicts.json")


def _load_all(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return raw
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def get_verdict(key: str, path: Path = _STORE_PATH) -> dict | None:
    """Читает вердикт по ключу '{tender_id}|{catalog_id}'.

    Args:
        key: Ключ вида '{tender_id}|{catalog_id}'.
        path: Путь к JSON-файлу хранилища.

    Returns:
        Словарь вердикта или None если не найден.
    """
    return _load_all(path).get(key)


def save_verdict(key: str, verdict: dict, path: Path = _STORE_PATH) -> None:
    """Сохраняет вердикт атомарно. Перезаписывает при совпадении ключа.

    Args:
        key: Ключ вида '{tender_id}|{catalog_id}'.
        verdict: Словарь вердикта (§3 дизайна Gate 8.2).
        path: Путь к JSON-файлу хранилища.
    """
    store = _load_all(path)
    store[key] = verdict
    atomic_write_json(path, store)
