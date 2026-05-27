from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def get_smtp_config() -> dict | None:
    """Читает SMTP-конфигурацию из переменных окружения (мост из secrets.toml [smtp]).

    Returns:
        Словарь host/port/user/password/from_addr/starttls или None если host не задан.
    """
    host = os.environ.get("SMTP_HOST")
    if not host:
        return None
    return {
        "host":      host,
        "port":      int(os.environ.get("SMTP_PORT", "587")),
        "user":      os.environ.get("SMTP_USER", ""),
        "password":  os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM_ADDR") or os.environ.get("SMTP_USER", ""),
        "starttls":  os.environ.get("SMTP_STARTTLS", "true").lower() != "false",
    }


def test_connection(cfg: dict) -> dict:
    """Проверяет SMTP-соединение и авторизацию (аналог get_me для Telegram).

    Args:
        cfg: Словарь из get_smtp_config().

    Returns:
        {"ok": bool, "error": str | None}
    """
    try:
        if cfg["starttls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=5) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                if cfg["user"]:
                    s.login(cfg["user"], cfg["password"])
        else:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=5) as s:
                if cfg["user"]:
                    s.login(cfg["user"], cfg["password"])
        return {"ok": True, "error": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def send_email(
    cfg: dict,
    to_addr: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> dict:
    """Отправляет одно письмо через smtplib (аналог send_message для Telegram).

    Args:
        cfg: Словарь из get_smtp_config().
        to_addr: Email получателя.
        subject: Тема письма.
        html_body: HTML-версия тела.
        text_body: Plain-text версия тела (fallback).

    Returns:
        {"ok": bool, "error": str | None}
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg["from_addr"]
        msg["To"]      = to_addr
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html",  "utf-8"))

        if cfg["starttls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=5) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                if cfg["user"]:
                    s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["from_addr"], to_addr, msg.as_string())
        else:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx, timeout=5) as s:
                if cfg["user"]:
                    s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["from_addr"], to_addr, msg.as_string())

        return {"ok": True, "error": None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _format_nmc(value) -> str:
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


def build_email_body(
    event: str,
    tender: dict,
    catalog: dict,
    decision: dict,
) -> tuple[str, str, str]:
    """Формирует тему, HTML-тело и plain-text тело email-уведомления.

    Логически идентично build_message() в telegram_alerts, без Telegram HTML-тегов.

    Args:
        event: Тип события — "participate", "skip", "ask".
        tender: Данные тендера (id, region, price_max, deadline_days).
        catalog: Данные SKU (part_number, name/description).
        decision: Контекст решения (comment / reason+note / question+score).

    Returns:
        Кортеж (subject, html_body, text_body).
    """
    _HEADERS = {
        "participate": "Участвуем",
        "skip":        "Пропускаем",
        "ask":         "Запрос мнения",
    }
    header    = _HEADERS.get(event, event)
    tender_id = str(tender.get("id", "—"))
    region    = str(tender.get("region", "—"))
    nmc       = _format_nmc(tender.get("price_max"))
    dd        = tender.get("deadline_days")
    deadline  = f"{dd} дн." if dd is not None else "—"
    pn        = str(catalog.get("part_number", "—"))
    sku_name  = str(catalog.get("name") or catalog.get("description") or "—")

    subject = f"[GoldenMatch] {header} — Тендер {tender_id}"

    rows_html = [
        f"<tr><td><b>Тендер</b></td><td>{tender_id}</td></tr>",
        f"<tr><td><b>Регион</b></td><td>{region}</td></tr>",
        f"<tr><td><b>НМЦ</b></td><td>{nmc}</td></tr>",
        f"<tr><td><b>Дедлайн</b></td><td>{deadline}</td></tr>",
        f"<tr><td><b>Позиция</b></td><td>{pn} — {sku_name}</td></tr>",
    ]
    lines_text = [
        f"=== {header} ===",
        "",
        f"Тендер:   {tender_id}",
        f"Регион:   {region}",
        f"НМЦ:      {nmc}",
        f"Дедлайн:  {deadline}",
        "",
        f"Позиция:  {pn} — {sku_name}",
    ]

    if event == "participate":
        comment = str(decision.get("comment", ""))
        if comment:
            rows_html.append(f"<tr><td><b>Комментарий</b></td><td>{comment}</td></tr>")
            lines_text += ["", f"Комментарий: {comment}"]
    elif event == "skip":
        reason = str(decision.get("reason", "—"))
        note   = str(decision.get("note", ""))
        rows_html.append(f"<tr><td><b>Причина</b></td><td>{reason}</td></tr>")
        lines_text += ["", f"Причина: {reason}"]
        if note:
            rows_html.append(f"<tr><td><b>Примечание</b></td><td>{note}</td></tr>")
            lines_text.append(f"Примечание: {note}")
    elif event == "ask":
        question = str(decision.get("question", ""))
        score    = decision.get("score")
        if question:
            rows_html.append(f"<tr><td><b>Вопрос</b></td><td>{question}</td></tr>")
            lines_text += ["", f"Вопрос: {question}"]
        if score is not None:
            rows_html.append(f"<tr><td><b>Score</b></td><td>{score:.2f}</td></tr>")
            lines_text.append(f"Score: {score:.2f}")

    html_body = f"<h2>{header}</h2><table>{''.join(rows_html)}</table>"
    return subject, html_body, "\n".join(lines_text)


def notify_email(
    event: str,
    recipients: list[dict],
    tender: dict,
    catalog: dict,
    decision: dict,
    cfg: dict | None = None,
    *,
    email_enabled: bool = True,
) -> dict:
    """Диспетчер email-уведомлений. Никогда не бросает исключение.

    Зеркало telegram_alerts.notify() — идентичный формат возврата.

    Args:
        event: Тип события — "participate", "skip", "ask".
        recipients: [{"name": str, "email": str, "enabled": bool}, ...]
        tender: Данные тендера.
        catalog: Данные SKU.
        decision: Контекст решения.
        cfg: SMTP-конфиг из get_smtp_config() (по умолчанию вызывается автоматически).
        email_enabled: Мастер-тумблер из channel_flags; False → skipped_by_settings.

    Returns:
        {"mode": "dry_run"|"skipped_by_settings"|"live", "sent": list[str], "results": list[dict]}
    """
    if cfg is None:
        cfg = get_smtp_config()

    active = [r for r in recipients if r.get("enabled")]

    if not cfg:
        for r in active:
            logger.info(
                "DRY-RUN email: было бы отправлено на %s (%s)",
                r["name"],
                r.get("email", ""),
            )
        return {
            "mode": "dry_run",
            "sent": [],
            "results": [{"channel": r["name"], "status": "dry_run", "error": None} for r in active],
        }

    if not email_enabled:
        return {
            "mode": "skipped_by_settings",
            "sent": [],
            "results": [{"channel": r["name"], "status": "skipped", "error": None} for r in active],
        }

    subject, html_body, text_body = build_email_body(event, tender, catalog, decision)

    results = []
    sent: list[str] = []
    for r in active:
        to_addr = r.get("email", "")
        if not to_addr:
            results.append({"channel": r["name"], "status": "failed", "error": "email адрес не задан"})
            continue
        try:
            res = send_email(cfg, to_addr, subject, html_body, text_body)
            if res["ok"]:
                results.append({"channel": r["name"], "status": "sent",   "error": None})
                sent.append(r["name"])
            else:
                results.append({"channel": r["name"], "status": "failed", "error": res["error"]})
        except Exception as exc:
            results.append({"channel": r["name"], "status": "failed", "error": str(exc)})

    return {"mode": "live", "sent": sent, "results": results}
