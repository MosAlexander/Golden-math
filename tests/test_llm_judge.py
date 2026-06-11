from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID

import pytest
import requests

from src.storage import atomic_write_json
from src import llm_judge_config
from src import llm_verdicts_store as store
from src.llm_judge import (
    TEMPERATURE,
    GigaChatProvider,
    YandexGPTProvider,
    _parse_json,
    judge_pair,
    check_connection,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

SAMPLE_PAIR = {
    "tender_id": "TG-001",
    "catalog_id": "SKU-007",
    "tender_name": "IGBT CM1000E3U 34A/1700V",
    "catalog_pn": "CM1000E3U-34NF",
    "catalog_mfr": "Mitsubishi",
    "match_probability": 0.857,
}


def _mock_oauth(token: str = "tok-123") -> MagicMock:
    m = MagicMock()
    m.json.return_value = {"access_token": token}
    m.raise_for_status.return_value = None
    return m


def _mock_chat(
    is_match: bool,
    confidence: str = "high",
    reasoning: str = "PN совпадает",
) -> MagicMock:
    content = json.dumps(
        {"is_match": is_match, "confidence": confidence, "reasoning": reasoning}
    )
    m = MagicMock()
    m.json.return_value = {"choices": [{"message": {"content": content}}]}
    m.raise_for_status.return_value = None
    return m


def _enable_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.llm_judge_config.is_enabled", lambda *a, **kw: True)
    monkeypatch.setattr("src.llm_judge_config.get_timeout", lambda *a, **kw: 5)
    monkeypatch.setattr("src.llm_judge_config.get_provider_name", lambda *a, **kw: "gigachat")
    monkeypatch.setattr("src.llm_judge_config.get_model", lambda *a, **kw: "GigaChat-Pro")
    monkeypatch.setenv("GIGACHAT_CA_BUNDLE", "")
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "dGVzdA==")
    monkeypatch.setenv("GIGACHAT_SCOPE", "GIGACHAT_API_B2B")


def _make_provider(monkeypatch: pytest.MonkeyPatch, ca_bundle: str = "") -> GigaChatProvider:
    monkeypatch.setenv("GIGACHAT_CA_BUNDLE", ca_bundle)
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "dGVzdA==")
    return GigaChatProvider(model="GigaChat-Pro", scope="GIGACHAT_API_B2B", ca_bundle=ca_bundle)


# ── Storage helper (8.2.0) ────────────────────────────────────────────────────

def test_atomic_write_creates_dir(tmp_path):
    target = tmp_path / "nested" / "dir" / "output.json"
    atomic_write_json(target, {"key": "value"})
    assert target.exists()


def test_atomic_write_valid_json(tmp_path):
    target = tmp_path / "output.json"
    data = {"ru": "привет", "nested": [1, 2, 3]}
    atomic_write_json(target, data)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == data
    raw = target.read_text(encoding="utf-8")
    assert "привет" in raw  # ensure_ascii=False
    assert "\n  " in raw    # indent=2


# ── llm_judge_config (8.2.2) ─────────────────────────────────────────────────

def test_llm_config_load_missing_returns_default(tmp_path):
    cfg = llm_judge_config.load(tmp_path / "llm_config.json")
    assert cfg["enabled"] is False
    assert cfg["provider"] == "gigachat"
    assert cfg["model"] == "GigaChat-Pro"
    assert cfg["timeout_sec"] == 5


def test_llm_config_save_load_roundtrip(tmp_path):
    path = tmp_path / "llm_config.json"
    data = {"enabled": True, "provider": "gigachat", "model": "GigaChat-Lite", "timeout_sec": 3}
    llm_judge_config.save(data, path)
    loaded = llm_judge_config.load(path)
    assert loaded == data


def test_llm_config_is_enabled_default_false(tmp_path):
    assert llm_judge_config.is_enabled(tmp_path / "missing.json") is False


# ── llm_verdicts_store (8.2.3) ───────────────────────────────────────────────

def test_store_save_then_get(tmp_path):
    path = tmp_path / "verdicts.json"
    verdict = {"status": "ok", "is_match": True, "confidence": "high", "reasoning": "PN совпадает"}
    store.save_verdict("t1|c1", verdict, path)
    assert store.get_verdict("t1|c1", path) == verdict


def test_store_get_missing_returns_none(tmp_path):
    path = tmp_path / "verdicts.json"
    assert store.get_verdict("missing|key", path) is None


def test_store_save_atomic_no_partial(tmp_path):
    path = tmp_path / "verdicts.json"
    store.save_verdict("t1|c1", {"status": "ok"}, path)
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_store_corrupt_file_fallback(tmp_path):
    path = tmp_path / "verdicts.json"
    path.write_text("not json {{{{", encoding="utf-8")
    assert store.get_verdict("t1|c1", path) is None
    store.save_verdict("t1|c1", {"status": "ok"}, path)
    assert store.get_verdict("t1|c1", path) == {"status": "ok"}


def test_store_key_format(tmp_path):
    path = tmp_path / "verdicts.json"
    tender_id, catalog_id = "TG-2024-001", "SKU-IGBT-007"
    key = f"{tender_id}|{catalog_id}"
    store.save_verdict(key, {"status": "ok"}, path)
    assert store.get_verdict(key, path) is not None
    assert store.get_verdict(f"{tender_id}|wrong", path) is None


# ── _parse_json (8.2.6) ──────────────────────────────────────────────────────

def test_parse_json_valid_json():
    r = _parse_json('{"is_match": true, "confidence": "high", "reasoning": "PN совпадает"}')
    assert r["ok"] is True
    assert r["is_match"] is True
    assert r["confidence"] == "high"
    assert r["reasoning"] == "PN совпадает"


def test_parse_json_markdown_fence():
    fenced = '```json\n{"is_match": false, "confidence": "low", "reasoning": "разные"}\n```'
    r = _parse_json(fenced)
    assert r["ok"] is True
    assert r["is_match"] is False


def test_parse_json_not_json_returns_invalid():
    r = _parse_json("вот мой ответ: нет")
    assert r["ok"] is False
    assert "error" in r


def test_parse_json_missing_field_returns_invalid():
    r = _parse_json('{"is_match": true, "confidence": "high"}')  # no reasoning
    assert r["ok"] is False


def test_parse_json_wrong_type_is_match_string():
    r = _parse_json('{"is_match": "true", "confidence": "high", "reasoning": "ok"}')
    assert r["ok"] is False
    assert "is_match" in r["error"]


# ── GigaChatProvider._get_token (8.2.6) ──────────────────────────────────────

def test_get_token_ok(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr("requests.post", lambda *a, **kw: _mock_oauth("my-token"))
    assert provider._get_token() == "my-token"


def test_get_token_sends_rquid_uuid4(monkeypatch):
    provider = _make_provider(monkeypatch)
    captured: dict = {}

    def fake_post(url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        return _mock_oauth()

    monkeypatch.setattr("requests.post", fake_post)
    provider._get_token()
    rquid = captured["headers"].get("RqUID", "")
    parsed = UUID(rquid)  # raises ValueError if not a valid UUID
    assert parsed.version == 4


def test_get_token_401_raises(monkeypatch):
    provider = _make_provider(monkeypatch)
    err_resp = MagicMock()
    err_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
    monkeypatch.setattr("requests.post", lambda *a, **kw: err_resp)
    with pytest.raises(requests.exceptions.HTTPError):
        provider._get_token()


def test_get_token_uses_ca_bundle(monkeypatch):
    provider = _make_provider(monkeypatch, ca_bundle="/fake/ca.pem")
    captured: dict = {}

    def fake_post(url, **kwargs):
        captured["verify"] = kwargs.get("verify")
        return _mock_oauth()

    monkeypatch.setattr("requests.post", fake_post)
    provider._get_token()
    assert captured["verify"] == "/fake/ca.pem"


# ── GigaChatProvider.judge (8.2.6) ───────────────────────────────────────────

def test_provider_judge_ok_match(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(True, "high", "PN совпадает"),
    ]))
    result = provider.judge(SAMPLE_PAIR, timeout_sec=5)
    assert result["is_match"] is True
    assert result["confidence"] == "high"


def test_provider_judge_ok_nomatch(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(False, "medium", "Разные модели"),
    ]))
    result = provider.judge(SAMPLE_PAIR, timeout_sec=5)
    assert result["is_match"] is False


def test_provider_judge_timeout(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(
        side_effect=requests.exceptions.Timeout()
    ))
    v = judge_pair(SAMPLE_PAIR)
    assert v["status"] == "timeout"


def test_provider_judge_http_error_500(monkeypatch):
    _enable_llm(monkeypatch)
    err_resp = MagicMock()
    err_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[_mock_oauth(), err_resp]))
    v = judge_pair(SAMPLE_PAIR)
    assert v["status"] == "error"


def test_provider_judge_sends_only_three_fields(monkeypatch):
    provider = _make_provider(monkeypatch)
    captured: dict = {}

    def fake_post(url, **kwargs):
        if "chat" in url:
            captured["json"] = kwargs.get("json", {})
            return _mock_chat(True)
        return _mock_oauth()

    monkeypatch.setattr("requests.post", fake_post)
    provider.judge({**SAMPLE_PAIR, "match_probability": 0.857}, timeout_sec=5)

    messages = captured["json"]["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "CM1000E3U 34A/1700V" in user_content   # tender_name
    assert "CM1000E3U-34NF" in user_content         # catalog_pn
    assert "Mitsubishi" in user_content             # catalog_mfr
    assert "0.857" not in user_content              # score НЕ передаётся модели


def test_provider_judge_uses_temperature_const(monkeypatch):
    provider = _make_provider(monkeypatch)
    captured: dict = {}

    def fake_post(url, **kwargs):
        if "chat" in url:
            captured["json"] = kwargs.get("json", {})
            return _mock_chat(True)
        return _mock_oauth()

    monkeypatch.setattr("requests.post", fake_post)
    provider.judge(SAMPLE_PAIR, timeout_sec=5)
    assert captured["json"]["temperature"] == TEMPERATURE


def test_yandexgpt_not_implemented():
    with pytest.raises(NotImplementedError):
        YandexGPTProvider().judge({}, timeout_sec=5)


# ── judge_pair facade (8.2.6) ─────────────────────────────────────────────────

def test_facade_disabled_no_network(monkeypatch):
    monkeypatch.setattr("src.llm_judge_config.is_enabled", lambda *a, **kw: False)
    called = []
    monkeypatch.setattr("requests.post", lambda *a, **kw: called.append(1))
    v = judge_pair(SAMPLE_PAIR)
    assert v["status"] == "error"
    assert "отключён" in v["reasoning"]
    assert called == []


def test_facade_never_raises(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(
        side_effect=RuntimeError("unexpected boom")
    ))
    try:
        v = judge_pair(SAMPLE_PAIR)
    except Exception:
        pytest.fail("judge_pair raised an exception")
    assert isinstance(v, dict)
    assert "status" in v


def test_facade_fills_metadata(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(True),
    ]))
    v = judge_pair(SAMPLE_PAIR)
    assert v["model"] == "GigaChat-Pro"
    assert v["prompt_version"] == 1
    assert v["created_at"]
    assert isinstance(v["latency_ms"], int)


def test_facade_sets_scored_at_probability(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(True),
    ]))
    v = judge_pair({**SAMPLE_PAIR, "match_probability": 0.831})
    assert v["scored_at_probability"] == 0.831


def test_facade_disagree_flag(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(False, "high", "Разные компоненты"),
    ]))
    v = judge_pair({**SAMPLE_PAIR, "match_probability": 0.80})
    assert v["status"] == "ok"
    assert v["is_match"] is False
    assert v["splink_llm_disagree"] is True


def test_facade_disagree_false_when_match(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(True, "high"),
    ]))
    v = judge_pair(SAMPLE_PAIR)
    assert v["splink_llm_disagree"] is False


def test_facade_disagree_false_when_error(monkeypatch):
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(
        side_effect=requests.exceptions.Timeout()
    ))
    v = judge_pair(SAMPLE_PAIR)
    assert v["status"] == "timeout"
    assert v["splink_llm_disagree"] is False


# ── ВОРОТА (8.2.6) ────────────────────────────────────────────────────────────

def test_llm_verdict_never_changes_decision(monkeypatch):
    """LLM verdict must NEVER mutate pair['decision'] or results[]. Инвариант №3."""
    _enable_llm(monkeypatch)
    monkeypatch.setattr("requests.post", MagicMock(side_effect=[
        _mock_oauth(), _mock_chat(True, "high", "PN совпадает точно"),
    ]))

    results = [
        {
            "tender_id": "TG-001",
            "catalog_id": "SKU-007",
            "decision": "borderline",
            "match_probability": 0.857,
        }
    ]
    best_match = results[0]
    pair = {
        "tender_id": best_match["tender_id"],
        "catalog_id": best_match["catalog_id"],
        "tender_name": "IGBT CM1000E3U",
        "catalog_pn": "CM1000E3U-34NF",
        "catalog_mfr": "Mitsubishi",
        "match_probability": best_match["match_probability"],
    }
    results_snapshot = [dict(r) for r in results]

    verdict = judge_pair(pair)

    assert verdict["status"] == "ok"
    assert verdict["is_match"] is True

    # Инвариант №3: decision и results[] не мутированы
    assert best_match["decision"] == "borderline"
    assert results == results_snapshot
    assert "decision" not in verdict


# ── Smoke (ручной, skipif) ────────────────────────────────────────────────────

@pytest.mark.skipif(
    not os.getenv("GIGACHAT_CREDENTIALS"),
    reason="no GIGACHAT_CREDENTIALS in env — skipped in CI",
)
def test_gigachat_live_smoke():
    """Боевой OAuth-пинг. Запускать вручную при наличии credentials."""
    result = check_connection()
    assert result["ok"] is True, f"GigaChat OAuth failed: {result['error']}"
