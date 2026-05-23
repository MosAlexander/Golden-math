from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CHANNELS_PATH = Path("data/channels.json")
DEFAULT_CONFIG: dict = {
    "channels": [],
    "events": {"participate": True, "ask": True, "skip": False},
}


def load_config(path: Path = CHANNELS_PATH) -> dict:
    """Читает конфиг из JSON-файла. При отсутствии или битом JSON — дефолт.

    Args:
        path: Путь к JSON-файлу конфига.

    Returns:
        Словарь с ключами channels и events (всегда оба присутствуют).
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return copy.deepcopy(DEFAULT_CONFIG)
        result = copy.deepcopy(DEFAULT_CONFIG)
        if "channels" in raw:
            result["channels"] = raw["channels"]
        if "events" in raw:
            result["events"].update(raw["events"])
        return result
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict, path: Path = CHANNELS_PATH) -> None:
    """Записывает конфиг в JSON-файл. Создаёт директорию при необходимости.

    Args:
        config: Словарь конфига.
        path: Путь к JSON-файлу.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_chat_id(chat_id: str) -> bool:
    """Валидирует Telegram chat_id.

    Args:
        chat_id: Строка вида -1001234567890, 123456 или @username.

    Returns:
        True если формат корректен, иначе False.
    """
    if not chat_id:
        return False
    if re.fullmatch(r"-?\d+", chat_id):
        return True
    if re.fullmatch(r"@[a-zA-Z0-9_]+", chat_id):
        return True
    return False


def _next_id(channels: list[dict]) -> str:
    ns = []
    for ch in channels:
        ch_id = ch.get("id", "")
        if isinstance(ch_id, str) and ch_id.startswith("ch_"):
            try:
                ns.append(int(ch_id[3:]))
            except ValueError:
                pass
    return f"ch_{max(ns, default=0) + 1}"


def add_channel(config: dict, name: str, chat_id: str) -> dict:
    """Добавляет новый канал. Генерирует id вида ch_{N} (max+1, не конфликтует после удалений).

    Args:
        config: Текущий конфиг.
        name: Название канала.
        chat_id: Telegram chat_id или @username.

    Returns:
        Новый конфиг с добавленным каналом.

    Raises:
        ValueError: Если name пустой после strip или chat_id невалидный.
    """
    if not name.strip():
        raise ValueError("Название канала не может быть пустым")
    if not validate_chat_id(chat_id):
        raise ValueError(f"Невалидный chat_id: {chat_id!r}")
    new_config = copy.deepcopy(config)
    channel_id = _next_id(new_config["channels"])
    new_config["channels"].append({
        "id": channel_id,
        "name": name.strip(),
        "chat_id": chat_id,
        "enabled": True,
    })
    return new_config


def update_channel(
    config: dict,
    channel_id: str,
    *,
    name: str | None = None,
    chat_id: str | None = None,
) -> dict:
    """Обновляет имя и/или chat_id канала по id.

    Args:
        config: Текущий конфиг.
        channel_id: id канала для обновления.
        name: Новое название (опционально).
        chat_id: Новый chat_id (опционально).

    Returns:
        Новый конфиг.

    Raises:
        ValueError: Если канал не найден или новый chat_id невалидный.
    """
    if name is not None and not name.strip():
        raise ValueError("Название канала не может быть пустым")
    if chat_id is not None and not validate_chat_id(chat_id):
        raise ValueError(f"Невалидный chat_id: {chat_id!r}")
    new_config = copy.deepcopy(config)
    for ch in new_config["channels"]:
        if ch["id"] == channel_id:
            if name is not None:
                ch["name"] = name.strip()
            if chat_id is not None:
                ch["chat_id"] = chat_id
            return new_config
    raise ValueError(f"Канал не найден: {channel_id!r}")


def delete_channel(config: dict, channel_id: str) -> dict:
    """Удаляет канал по id.

    Args:
        config: Текущий конфиг.
        channel_id: id канала для удаления.

    Returns:
        Новый конфиг без удалённого канала.

    Raises:
        ValueError: Если канал не найден.
    """
    new_config = copy.deepcopy(config)
    before = len(new_config["channels"])
    new_config["channels"] = [ch for ch in new_config["channels"] if ch["id"] != channel_id]
    if len(new_config["channels"]) == before:
        raise ValueError(f"Канал не найден: {channel_id!r}")
    return new_config


def toggle_channel(config: dict, channel_id: str, enabled: bool) -> dict:
    """Включает или выключает канал.

    Args:
        config: Текущий конфиг.
        channel_id: id канала.
        enabled: Новое состояние.

    Returns:
        Новый конфиг.

    Raises:
        ValueError: Если канал не найден.
    """
    new_config = copy.deepcopy(config)
    for ch in new_config["channels"]:
        if ch["id"] == channel_id:
            ch["enabled"] = enabled
            return new_config
    raise ValueError(f"Канал не найден: {channel_id!r}")


def set_event(config: dict, event: str, enabled: bool) -> dict:
    """Устанавливает флаг события.

    Args:
        config: Текущий конфиг.
        event: Название события (participate | ask | skip).
        enabled: Новое значение флага.

    Returns:
        Новый конфиг.

    Raises:
        ValueError: Если событие неизвестно.
    """
    _VALID = {"participate", "ask", "skip"}
    if event not in _VALID:
        raise ValueError(f"Неизвестное событие: {event!r}. Допустимые: {_VALID}")
    new_config = copy.deepcopy(config)
    new_config["events"][event] = enabled
    return new_config


def enabled_channels(config: dict) -> list[dict]:
    """Возвращает список активных каналов (пригоден для telegram_alerts.notify).

    Args:
        config: Текущий конфиг.

    Returns:
        Список каналов с enabled=True.
    """
    return [ch for ch in config.get("channels", []) if ch.get("enabled")]


def is_event_enabled(config: dict, event: str) -> bool:
    """Проверяет, включено ли событие.

    Args:
        config: Текущий конфиг.
        event: Название события.

    Returns:
        True если событие включено, False если выключено или неизвестно.
    """
    return bool(config.get("events", {}).get(event, False))
