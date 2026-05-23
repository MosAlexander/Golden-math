from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests as req_lib

from src.telegram_alerts import build_message, get_me, get_token, notify, send_message

# ── Shared fixtures ───────────────────────────────────────────────────────────

TENDER = {
    "id": "T-A01",
    "region": "Москва",
    "price_max": 150000,
    "deadline_days": 14,
}

CATALOG = {
    "part_number": "CM1000E3U-34NF",
    "name": "IGBT модуль 1000А",
}

DECISION_PARTICIPATE = {"comment": "Есть на складе"}
DECISION_SKIP        = {"reason": "Нет аналога", "note": "Проверить у поставщика"}
DECISION_ASK         = {"question": "Подходит ли PN?", "score": 0.85}

CHANNELS_ONE_ENABLED = [
    {"name": "Менеджер", "chat_id": "-100111", "enabled": True},
    {"name": "Архив",    "chat_id": "-100222", "enabled": False},
]


# ── get_token ─────────────────────────────────────────────────────────────────

def test_get_token_returns_none_without_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert get_token() is None


def test_get_token_returns_value_with_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    assert get_token() == "test-token-123"


def test_get_token_empty_string_treated_as_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    assert get_token() is None


# ── get_me ────────────────────────────────────────────────────────────────────

def test_get_me_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": {"username": "radal_match_bot", "id": 123},
    }
    with patch("src.telegram_alerts.requests.get", return_value=mock_resp) as mock_get:
        result = get_me("fake-token")

    mock_get.assert_called_once()
    assert result["ok"] is True
    assert result["bot_username"] == "radal_match_bot"
    assert result["error"] is None


def test_get_me_api_error_returns_ok_false():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "Unauthorized"}
    with patch("src.telegram_alerts.requests.get", return_value=mock_resp):
        result = get_me("bad-token")

    assert result["ok"] is False
    assert result["bot_username"] is None
    assert result["error"] == "Unauthorized"


def test_get_me_network_error_no_exception():
    with patch("src.telegram_alerts.requests.get", side_effect=ConnectionError("timeout")):
        result = get_me("any-token")

    assert result["ok"] is False
    assert result["bot_username"] is None
    assert result["error"] is not None


def test_get_me_timeout_no_exception():
    with patch("src.telegram_alerts.requests.get", side_effect=req_lib.exceptions.Timeout):
        result = get_me("any-token")

    assert result["ok"] is False


# ── send_message ──────────────────────────────────────────────────────────────

def test_send_message_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 42}}
    with patch("src.telegram_alerts.requests.post", return_value=mock_resp):
        result = send_message("fake-token", "-100123", "Hello")

    assert result["ok"] is True
    assert result["error"] is None


def test_send_message_api_error_returns_ok_false():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request: chat not found"}
    with patch("src.telegram_alerts.requests.post", return_value=mock_resp):
        result = send_message("fake-token", "bad-chat", "Hello")

    assert result["ok"] is False
    assert "Bad Request" in result["error"]


def test_send_message_timeout_no_exception():
    with patch("src.telegram_alerts.requests.post", side_effect=req_lib.exceptions.Timeout):
        result = send_message("fake-token", "-100", "Hello")

    assert result["ok"] is False
    assert result["error"] is not None


def test_send_message_connection_error_no_exception():
    with patch("src.telegram_alerts.requests.post", side_effect=ConnectionError("refused")):
        result = send_message("t", "-1", "x")

    assert result["ok"] is False


# ── build_message ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("event,decision", [
    ("participate", DECISION_PARTICIPATE),
    ("skip",        DECISION_SKIP),
    ("ask",         DECISION_ASK),
])
def test_build_message_contains_tender_id_and_pn(event, decision):
    text = build_message(event, TENDER, CATALOG, decision)
    assert text
    assert "T-A01" in text
    assert "CM1000E3U-34NF" in text


def test_build_message_html_escaping_in_comment():
    decision = {"comment": "<script>alert('xss')</script>"}
    text = build_message("participate", TENDER, CATALOG, decision)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_build_message_html_escaping_in_question():
    decision = {"question": "A & B > C", "score": 0.80}
    text = build_message("ask", TENDER, CATALOG, decision)
    assert "&amp;" in text
    assert "&gt;" in text


def test_build_message_participate_includes_comment():
    text = build_message("participate", TENDER, CATALOG, {"comment": "Готовы поставить"})
    assert "Готовы поставить" in text


def test_build_message_skip_includes_reason_and_note():
    text = build_message("skip", TENDER, CATALOG, DECISION_SKIP)
    assert "Нет аналога" in text
    assert "Проверить у поставщика" in text


def test_build_message_ask_includes_question_and_score():
    text = build_message("ask", TENDER, CATALOG, DECISION_ASK)
    assert "Подходит ли PN?" in text
    assert "0.85" in text


def test_build_message_participate_empty_comment_no_label():
    text = build_message("participate", TENDER, CATALOG, {"comment": ""})
    assert "Комментарий" not in text


# ── notify — dry-run (no token) ───────────────────────────────────────────────

def test_notify_dry_run_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    result = notify("participate", CHANNELS_ONE_ENABLED, TENDER, CATALOG, DECISION_PARTICIPATE)

    assert result["mode"] == "dry_run"
    assert result["sent"] == []
    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "dry_run"


def test_notify_dry_run_does_not_call_send(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with patch("src.telegram_alerts.send_message") as mock_send:
        notify("participate", CHANNELS_ONE_ENABLED, TENDER, CATALOG, DECISION_PARTICIPATE)
    mock_send.assert_not_called()


def test_notify_dry_run_explicit_none_token():
    result = notify("skip", CHANNELS_ONE_ENABLED, TENDER, CATALOG, DECISION_SKIP, token=None)
    # Без env-переменной тоже dry_run
    assert result["mode"] in ("dry_run", "live")  # live только если env задан


def test_notify_dry_run_only_enabled_in_results(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    channels = [
        {"name": "A", "chat_id": "-1", "enabled": True},
        {"name": "B", "chat_id": "-2", "enabled": False},
        {"name": "C", "chat_id": "-3", "enabled": False},
    ]
    result = notify("participate", channels, TENDER, CATALOG, DECISION_PARTICIPATE)
    assert len(result["results"]) == 1
    assert result["results"][0]["channel"] == "A"


# ── notify — live (with token) ────────────────────────────────────────────────

def test_notify_live_sent_and_failed():
    def fake_send(token, chat_id, text):
        return {"ok": chat_id == "-100111", "error": None if chat_id == "-100111" else "not found"}

    channels = [
        {"name": "Менеджер", "chat_id": "-100111", "enabled": True},
        {"name": "Резерв",   "chat_id": "-100999", "enabled": True},
    ]
    with patch("src.telegram_alerts.send_message", side_effect=fake_send):
        result = notify("skip", channels, TENDER, CATALOG, DECISION_SKIP, token="t")

    assert result["mode"] == "live"
    assert "Менеджер" in result["sent"]
    assert "Резерв" not in result["sent"]
    statuses = {r["channel"]: r["status"] for r in result["results"]}
    assert statuses["Менеджер"] == "sent"
    assert statuses["Резерв"] == "failed"


def test_notify_live_one_channel_exception_others_continue():
    calls: list[str] = []

    def fake_send(token, chat_id, text):
        calls.append(chat_id)
        if chat_id == "-100AAA":
            raise RuntimeError("boom")
        return {"ok": True, "error": None}

    channels = [
        {"name": "A", "chat_id": "-100AAA", "enabled": True},
        {"name": "B", "chat_id": "-100BBB", "enabled": True},
    ]
    with patch("src.telegram_alerts.send_message", side_effect=fake_send):
        result = notify("ask", channels, TENDER, CATALOG, DECISION_ASK, token="t")

    assert result["mode"] == "live"
    assert "-100AAA" in calls
    assert "-100BBB" in calls
    assert "B" in result["sent"]
    statuses = {r["channel"]: r["status"] for r in result["results"]}
    assert statuses["A"] == "failed"
    assert statuses["B"] == "sent"


def test_notify_live_only_enabled_channels_receive_send():
    channels = [
        {"name": "Активный", "chat_id": "-1", "enabled": True},
        {"name": "Выключен", "chat_id": "-2", "enabled": False},
        {"name": "Нулевой",  "chat_id": "-3", "enabled": False},
    ]
    with patch("src.telegram_alerts.send_message") as mock_send:
        mock_send.return_value = {"ok": True, "error": None}
        result = notify("participate", channels, TENDER, CATALOG, DECISION_PARTICIPATE, token="t")

    assert mock_send.call_count == 1
    assert result["sent"] == ["Активный"]


def test_notify_live_all_success():
    channels = [
        {"name": "C1", "chat_id": "-1", "enabled": True},
        {"name": "C2", "chat_id": "-2", "enabled": True},
    ]
    with patch("src.telegram_alerts.send_message", return_value={"ok": True, "error": None}):
        result = notify("participate", channels, TENDER, CATALOG, DECISION_PARTICIPATE, token="t")

    assert result["mode"] == "live"
    assert set(result["sent"]) == {"C1", "C2"}
    assert all(r["status"] == "sent" for r in result["results"])


def test_notify_never_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    # Передаём заведомо кривые данные — не должен упасть
    try:
        notify("unknown_event", [], {}, {}, {})
        notify("participate", [{"name": "X", "chat_id": None, "enabled": True}],
               {}, {}, {}, token="t")
    except Exception as exc:
        pytest.fail(f"notify raised: {exc}")


# ── build_message: форматирование реальных полей тендера ─────────────────────

def test_build_message_formats_nmc():
    base = {"id": "T-X", "region": "Москва", "deadline_days": 5}

    text_k = build_message("participate", {**base, "price_max": 150000}, CATALOG, DECISION_PARTICIPATE)
    assert "150 К ₽" in text_k

    text_m = build_message("participate", {**base, "price_max": 2_500_000}, CATALOG, DECISION_PARTICIPATE)
    assert "2.5 М ₽" in text_m

    text_zero = build_message("participate", {**base, "price_max": 0}, CATALOG, DECISION_PARTICIPATE)
    assert "НМЦ:</b> —" in text_zero

    text_none = build_message("participate", base, CATALOG, DECISION_PARTICIPATE)
    assert "НМЦ:</b> —" in text_none


def test_build_message_formats_deadline_days():
    base = {"id": "T-X", "region": "Москва", "price_max": 50000}

    text_days = build_message("participate", {**base, "deadline_days": 14}, CATALOG, DECISION_PARTICIPATE)
    assert "14 дн." in text_days

    text_none = build_message("participate", base, CATALOG, DECISION_PARTICIPATE)
    assert "Дедлайн:</b> —" in text_none
