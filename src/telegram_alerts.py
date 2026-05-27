from __future__ import annotations

import html
import logging
import os

import requests

logger = logging.getLogger(__name__)


def get_token() -> str | None:
    """Читает токен Telegram бота из переменной окружения.

    Returns:
        Строка токена или None если не задан/пустой.
    """
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def get_me(token: str) -> dict:
    """Проверяет валидность токена через Telegram Bot API getMe.

    Args:
        token: Telegram bot token.

    Returns:
        {"ok": bool, "bot_username": str | None, "error": str | None}
    """
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=5,
        )
        data = resp.json()
        if data.get("ok"):
            return {
                "ok": True,
                "bot_username": data["result"].get("username"),
                "error": None,
            }
        return {
            "ok": False,
            "bot_username": None,
            "error": data.get("description", "Unknown error"),
        }
    except Exception as exc:
        return {"ok": False, "bot_username": None, "error": str(exc)}


def send_message(token: str, chat_id: str, text: str) -> dict:
    """Отправляет HTML-сообщение в Telegram чат.

    Args:
        token: Telegram bot token.
        chat_id: ID чата получателя.
        text: Текст сообщения с HTML-разметкой.

    Returns:
        {"ok": bool, "error": str | None}
    """
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
        data = resp.json()
        if data.get("ok"):
            return {"ok": True, "error": None}
        return {"ok": False, "error": data.get("description", "Unknown error")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _format_nmc(value) -> str:
    """Форматирует НМЦ в читаемый вид (₽). Локальная копия логики _format_nmc из matching.py."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if not v:
        return "—"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f} М ₽"
    if v >= 1_000:
        return f"{v / 1_000:.0f} К ₽"
    return f"{v:.0f} ₽"


def build_message(event: str, tender: dict, catalog: dict, decision: dict) -> str:
    """Формирует HTML-текст Telegram-уведомления.

    Args:
        event: Тип события — "participate", "skip", "ask".
        tender: Данные тендера (id, region, price_max, deadline_days).
        catalog: Данные SKU (part_number, name/description).
        decision: Контекст решения (comment / reason+note / question+score).

    Returns:
        HTML-строка для Telegram sendMessage (parse_mode=HTML).
    """
    _HEADERS = {
        "participate": "✅ Участвуем",
        "skip":        "⏭ Пропускаем",
        "ask":         "❓ Запрос мнения",
    }
    header    = _HEADERS.get(event, html.escape(event))
    tender_id = html.escape(str(tender.get("id", "—")))
    region    = html.escape(str(tender.get("region", "—")))
    nmc       = _format_nmc(tender.get("price_max"))
    dd        = tender.get("deadline_days")
    deadline  = f"{dd} дн." if dd is not None else "—"
    pn        = html.escape(str(catalog.get("part_number", "—")))
    sku_name  = html.escape(str(catalog.get("name") or catalog.get("description") or "—"))

    lines = [
        f"<b>{header}</b>",
        "",
        f"<b>Тендер:</b> {tender_id}",
        f"<b>Регион:</b> {region}",
        f"<b>НМЦ:</b> {nmc}",
        f"<b>Дедлайн:</b> {deadline}",
        "",
        f"<b>Позиция:</b> {pn} — {sku_name}",
    ]

    if event == "participate":
        comment = html.escape(str(decision.get("comment", "")))
        if comment:
            lines += ["", f"<b>Комментарий:</b> {comment}"]
    elif event == "skip":
        reason = html.escape(str(decision.get("reason", "—")))
        note   = html.escape(str(decision.get("note", "")))
        lines += ["", f"<b>Причина:</b> {reason}"]
        if note:
            lines.append(f"<b>Примечание:</b> {note}")
    elif event == "ask":
        question = html.escape(str(decision.get("question", "")))
        if question:
            lines += ["", f"<b>Вопрос:</b> {question}"]
        score = decision.get("score")
        if score is not None:
            lines.append(f"<b>Score:</b> {score:.2f}")

    return "\n".join(lines)


def notify(
    event: str,
    channels: list[dict],
    tender: dict,
    catalog: dict,
    decision: dict,
    token: str | None = None,
    *,
    telegram_enabled: bool = True,
) -> dict:
    """Диспетчер уведомлений. Никогда не бросает исключение.

    Args:
        event: Тип события — "participate", "skip", "ask".
        channels: [{"name": str, "chat_id": str, "enabled": bool}, ...]
        tender: Данные тендера.
        catalog: Данные SKU.
        decision: Контекст решения.
        token: Telegram bot token (по умолчанию из get_token()).
        telegram_enabled: Мастер-тумблер из channel_flags; False → skipped_by_settings.

    Returns:
        {"mode": "dry_run"|"skipped_by_settings"|"live", "sent": list[str], "results": list[dict]}
    """
    if token is None:
        token = get_token()

    enabled = [ch for ch in channels if ch.get("enabled")]
    text = build_message(event, tender, catalog, decision)

    if not telegram_enabled:
        return {
            "mode": "skipped_by_settings",
            "sent": [],
            "results": [{"channel": ch["name"], "status": "skipped", "error": None} for ch in enabled],
        }

    if not token:
        for ch in enabled:
            logger.info(
                "DRY-RUN: было бы отправлено в %s (%s): %s",
                ch["name"],
                ch.get("chat_id", ""),
                text[:80],
            )
        return {
            "mode": "dry_run",
            "sent": [],
            "results": [{"channel": ch["name"], "status": "dry_run", "error": None} for ch in enabled],
        }

    results = []
    sent: list[str] = []
    for ch in enabled:
        try:
            res = send_message(token, ch["chat_id"], text)
            if res["ok"]:
                results.append({"channel": ch["name"], "status": "sent",   "error": None})
                sent.append(ch["name"])
            else:
                results.append({"channel": ch["name"], "status": "failed", "error": res.get("error")})
        except Exception as exc:
            results.append({"channel": ch["name"], "status": "failed", "error": str(exc)})

    return {"mode": "live", "sent": sent, "results": results}
