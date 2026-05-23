from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.channels_config import (
    DEFAULT_CONFIG,
    add_channel,
    delete_channel,
    enabled_channels,
    is_event_enabled,
    load_config,
    save_config,
    set_event,
    toggle_channel,
    update_channel,
    validate_chat_id,
)


# ── load_config ───────────────────────────────────────────────────────────────

def test_load_config_no_file_returns_default(tmp_path):
    cfg = load_config(tmp_path / "channels.json")
    assert cfg["channels"] == []
    assert cfg["events"] == DEFAULT_CONFIG["events"]


def test_load_config_broken_json_returns_default(tmp_path):
    f = tmp_path / "channels.json"
    f.write_text("not-json{{{", encoding="utf-8")
    cfg = load_config(f)
    assert cfg["channels"] == []
    assert "participate" in cfg["events"]


def test_load_config_partial_only_channels_events_filled(tmp_path):
    f = tmp_path / "channels.json"
    data = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "-1", "enabled": True}]}
    f.write_text(json.dumps(data), encoding="utf-8")
    cfg = load_config(f)
    assert len(cfg["channels"]) == 1
    assert cfg["events"] == DEFAULT_CONFIG["events"]


def test_load_config_reads_normally(tmp_path):
    data = {
        "channels": [{"id": "ch_1", "name": "Менеджеры", "chat_id": "-1001234567890", "enabled": True}],
        "events": {"participate": True, "ask": False, "skip": True},
    }
    f = tmp_path / "channels.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    cfg = load_config(f)
    assert cfg["channels"][0]["name"] == "Менеджеры"
    assert cfg["events"]["ask"] is False
    assert cfg["events"]["skip"] is True


def test_load_config_returns_deep_copy(tmp_path):
    cfg = load_config(tmp_path / "doesnt_exist.json")
    cfg["channels"].append({"id": "x"})
    assert DEFAULT_CONFIG["channels"] == []


# ── save_config + round-trip ──────────────────────────────────────────────────

def test_save_load_roundtrip(tmp_path):
    cfg = {
        "channels": [{"id": "ch_1", "name": "Менеджеры", "chat_id": "-1001234567890", "enabled": True}],
        "events": {"participate": True, "ask": True, "skip": False},
    }
    path = tmp_path / "channels.json"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded == cfg


def test_save_config_cyrillic_readable(tmp_path):
    cfg = {
        "channels": [{"id": "ch_1", "name": "Менеджеры", "chat_id": "-100", "enabled": True}],
        "events": {"participate": True, "ask": True, "skip": False},
    }
    path = tmp_path / "channels.json"
    save_config(cfg, path)
    raw = path.read_text(encoding="utf-8")
    assert "Менеджеры" in raw


def test_save_config_creates_parent_dir(tmp_path):
    path = tmp_path / "subdir" / "channels.json"
    save_config(DEFAULT_CONFIG, path)
    assert path.exists()


# ── validate_chat_id ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("chat_id", ["-1001234567890", "123456", "@radal_proc"])
def test_validate_chat_id_valid(chat_id):
    assert validate_chat_id(chat_id) is True


@pytest.mark.parametrize("chat_id", ["", None, "radal", "@", "abc123", "@bad-name"])
def test_validate_chat_id_invalid(chat_id):
    assert validate_chat_id(chat_id) is False


# ── add_channel ───────────────────────────────────────────────────────────────

def test_add_channel_generates_ch1_ch2():
    cfg = {"channels": [], "events": dict(DEFAULT_CONFIG["events"])}
    cfg = add_channel(cfg, "A", "123")
    assert cfg["channels"][0]["id"] == "ch_1"
    cfg = add_channel(cfg, "B", "-100222")
    assert cfg["channels"][1]["id"] == "ch_2"


def test_add_channel_after_delete_no_id_conflict():
    cfg = {"channels": [], "events": dict(DEFAULT_CONFIG["events"])}
    cfg = add_channel(cfg, "A", "111")    # ch_1
    cfg = add_channel(cfg, "B", "222")    # ch_2
    cfg = delete_channel(cfg, "ch_1")
    cfg = add_channel(cfg, "C", "333")    # must be ch_3, not ch_1
    ids = [ch["id"] for ch in cfg["channels"]]
    assert "ch_3" in ids
    assert ids.count("ch_2") == 1
    assert "ch_1" not in ids


def test_add_channel_empty_name_raises():
    cfg = {"channels": [], "events": {}}
    with pytest.raises(ValueError):
        add_channel(cfg, "  ", "123")


def test_add_channel_invalid_chat_id_raises():
    cfg = {"channels": [], "events": {}}
    with pytest.raises(ValueError):
        add_channel(cfg, "Test", "not-valid")


def test_add_channel_does_not_mutate_input():
    cfg = {"channels": [], "events": dict(DEFAULT_CONFIG["events"])}
    add_channel(cfg, "Test", "123")
    assert cfg["channels"] == []


def test_add_channel_enabled_true_by_default():
    cfg = {"channels": [], "events": {}}
    cfg2 = add_channel(cfg, "X", "456")
    assert cfg2["channels"][0]["enabled"] is True


# ── update_channel ────────────────────────────────────────────────────────────

def test_update_channel_name():
    cfg = {"channels": [{"id": "ch_1", "name": "Old", "chat_id": "123", "enabled": True}], "events": {}}
    cfg2 = update_channel(cfg, "ch_1", name="New")
    assert cfg2["channels"][0]["name"] == "New"
    assert cfg["channels"][0]["name"] == "Old"


def test_update_channel_chat_id():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    cfg2 = update_channel(cfg, "ch_1", chat_id="-100999")
    assert cfg2["channels"][0]["chat_id"] == "-100999"


def test_update_channel_not_found_raises():
    cfg = {"channels": [], "events": {}}
    with pytest.raises(ValueError):
        update_channel(cfg, "ch_999")


def test_update_channel_invalid_chat_id_raises():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    with pytest.raises(ValueError):
        update_channel(cfg, "ch_1", chat_id="not@valid")


def test_update_channel_empty_name_raises():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    with pytest.raises(ValueError, match="Название канала не может быть пустым"):
        update_channel(cfg, "ch_1", name="  ")


def test_update_channel_strips_name():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    cfg2 = update_channel(cfg, "ch_1", name="  Менеджеры  ")
    assert cfg2["channels"][0]["name"] == "Менеджеры"


# ── delete_channel ────────────────────────────────────────────────────────────

def test_delete_channel_removes():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    cfg2 = delete_channel(cfg, "ch_1")
    assert cfg2["channels"] == []


def test_delete_channel_not_found_raises():
    cfg = {"channels": [], "events": {}}
    with pytest.raises(ValueError):
        delete_channel(cfg, "ch_999")


def test_delete_channel_does_not_mutate_input():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    delete_channel(cfg, "ch_1")
    assert len(cfg["channels"]) == 1


# ── toggle_channel ────────────────────────────────────────────────────────────

def test_toggle_channel_enable():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": False}], "events": {}}
    cfg2 = toggle_channel(cfg, "ch_1", True)
    assert cfg2["channels"][0]["enabled"] is True


def test_toggle_channel_disable():
    cfg = {"channels": [{"id": "ch_1", "name": "X", "chat_id": "123", "enabled": True}], "events": {}}
    cfg2 = toggle_channel(cfg, "ch_1", False)
    assert cfg2["channels"][0]["enabled"] is False


def test_toggle_channel_not_found_raises():
    cfg = {"channels": [], "events": {}}
    with pytest.raises(ValueError):
        toggle_channel(cfg, "ch_999", True)


# ── set_event ─────────────────────────────────────────────────────────────────

def test_set_event_changes_flag():
    cfg = {"channels": [], "events": {"participate": True, "ask": True, "skip": False}}
    cfg2 = set_event(cfg, "skip", True)
    assert cfg2["events"]["skip"] is True
    assert cfg["events"]["skip"] is False


def test_set_event_unknown_raises():
    cfg = {"channels": [], "events": {"participate": True, "ask": True, "skip": False}}
    with pytest.raises(ValueError):
        set_event(cfg, "unknown_event", True)


# ── enabled_channels ──────────────────────────────────────────────────────────

def test_enabled_channels_returns_only_enabled():
    cfg = {
        "channels": [
            {"id": "ch_1", "name": "A", "chat_id": "1", "enabled": True},
            {"id": "ch_2", "name": "B", "chat_id": "2", "enabled": False},
            {"id": "ch_3", "name": "C", "chat_id": "3", "enabled": True},
        ],
        "events": {},
    }
    result = enabled_channels(cfg)
    names = [ch["name"] for ch in result]
    assert len(result) == 2
    assert "A" in names
    assert "C" in names
    assert "B" not in names


def test_enabled_channels_format_for_notify():
    cfg = {
        "channels": [{"id": "ch_1", "name": "Менеджеры", "chat_id": "-100", "enabled": True}],
        "events": {},
    }
    channels = enabled_channels(cfg)
    for ch in channels:
        assert "name" in ch
        assert "chat_id" in ch
        assert "enabled" in ch


# ── is_event_enabled ──────────────────────────────────────────────────────────

def test_is_event_enabled_true():
    cfg = {"channels": [], "events": {"participate": True, "ask": True, "skip": False}}
    assert is_event_enabled(cfg, "participate") is True
    assert is_event_enabled(cfg, "ask") is True


def test_is_event_enabled_false():
    cfg = {"channels": [], "events": {"participate": True, "ask": True, "skip": False}}
    assert is_event_enabled(cfg, "skip") is False


def test_is_event_enabled_unknown_returns_false():
    cfg = {"channels": [], "events": {"participate": True}}
    assert is_event_enabled(cfg, "nonexistent") is False


# ── integration: add → enabled_channels → notify (dry_run) ───────────────────

def test_integration_add_to_notify_dry_run(monkeypatch):
    from src.telegram_alerts import notify

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    cfg = {"channels": [], "events": dict(DEFAULT_CONFIG["events"])}
    cfg = add_channel(cfg, "Менеджеры", "-1001234567890")
    channels = enabled_channels(cfg)

    tender = {"id": "T-001", "region": "Москва", "price_max": 100_000, "deadline_days": 14}
    catalog = {"part_number": "CM1000E3U-34NF", "name": "IGBT модуль"}
    decision = {"comment": "Тест"}

    result = notify("participate", channels, tender, catalog, decision)
    assert result["mode"] == "dry_run"
    assert result["sent"] == []
