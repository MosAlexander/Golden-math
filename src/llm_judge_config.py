from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

from src.storage import atomic_write_json

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path("data/llm_config.json")

_DEFAULT: dict = {
    "enabled": False,
    "provider": "gigachat",
    "model": "GigaChat-Pro",
    "timeout_sec": 5,
}


def load(path: Path = _CONFIG_PATH) -> dict:
    """Читает конфиг LLM-judge. При отсутствии или битом JSON — дефолт.

    Args:
        path: Путь к JSON-файлу конфига.

    Returns:
        Словарь с полями enabled, provider, model, timeout_sec.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return copy.deepcopy(_DEFAULT)
        result = copy.deepcopy(_DEFAULT)
        result.update({k: v for k, v in raw.items() if k in _DEFAULT})
        return result
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return copy.deepcopy(_DEFAULT)


def save(config: dict, path: Path = _CONFIG_PATH) -> None:
    """Сохраняет конфиг LLM-judge атомарно.

    Args:
        config: Словарь конфига.
        path: Путь к JSON-файлу.
    """
    atomic_write_json(path, config)


def is_enabled(path: Path = _CONFIG_PATH) -> bool:
    """Returns True если LLM-judge включён.

    Args:
        path: Путь к файлу конфига.
    """
    return bool(load(path).get("enabled", False))


def get_provider_name(path: Path = _CONFIG_PATH) -> str:
    """Returns имя провайдера ('gigachat' | 'yandexgpt').

    Args:
        path: Путь к файлу конфига.
    """
    return str(load(path).get("provider", _DEFAULT["provider"]))


def get_model(path: Path = _CONFIG_PATH) -> str:
    """Returns имя модели (напр. 'GigaChat-Pro').

    Args:
        path: Путь к файлу конфига.
    """
    return str(load(path).get("model", _DEFAULT["model"]))


def get_timeout(path: Path = _CONFIG_PATH) -> int:
    """Returns таймаут в секундах (default 5, RULES §3).

    Args:
        path: Путь к файлу конфига.
    """
    return int(load(path).get("timeout_sec", _DEFAULT["timeout_sec"]))
