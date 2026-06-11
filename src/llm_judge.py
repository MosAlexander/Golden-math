from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone

import requests

from src import llm_judge_config
from src.llm_judge_prompts import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE, PROMPT_VERSION

logger = logging.getLogger(__name__)

TEMPERATURE = 0.1


class _InvalidResponseError(Exception):
    pass


class LLMJudgeProvider:
    name = "base"

    def judge(self, pair: dict, *, timeout_sec: int) -> dict:
        raise NotImplementedError


class GigaChatProvider(LLMJudgeProvider):
    name = "gigachat"
    OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    def __init__(self, *, model: str, scope: str, ca_bundle: str) -> None:
        self._model = model
        self._scope = scope
        self._ca_bundle = ca_bundle

    def _get_token(self) -> str:
        credentials = os.environ.get("GIGACHAT_CREDENTIALS", "")
        resp = requests.post(
            self.OAUTH_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": self._scope},
            verify=self._ca_bundle or True,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def judge(self, pair: dict, *, timeout_sec: int) -> dict:
        token = self._get_token()
        user_msg = JUDGE_USER_TEMPLATE.format(
            tender_name=pair.get("tender_name", ""),
            catalog_pn=pair.get("catalog_pn", ""),
            catalog_mfr=pair.get("catalog_mfr", ""),
        )
        resp = requests.post(
            self.CHAT_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": TEMPERATURE,
            },
            verify=self._ca_bundle or True,
            timeout=timeout_sec,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = _parse_json(content)
        if not parsed["ok"]:
            logger.warning("LLM invalid_response: %s", parsed["error"])
            raise _InvalidResponseError(parsed["error"])
        return {
            "is_match": parsed["is_match"],
            "confidence": parsed["confidence"],
            "reasoning": parsed["reasoning"],
            "model": self._model,
        }


class YandexGPTProvider(LLMJudgeProvider):
    name = "yandexgpt"

    def judge(self, pair: dict, *, timeout_sec: int) -> dict:
        raise NotImplementedError("YandexGPT — Gate 9+")


def get_provider() -> LLMJudgeProvider:
    """Фабрика провайдера из конфига."""
    provider_name = llm_judge_config.get_provider_name()
    model = llm_judge_config.get_model()
    scope = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_B2B")
    ca_bundle = os.environ.get("GIGACHAT_CA_BUNDLE", "")
    if provider_name == "gigachat":
        return GigaChatProvider(model=model, scope=scope, ca_bundle=ca_bundle)
    if provider_name == "yandexgpt":
        return YandexGPTProvider()
    raise ValueError(f"Неизвестный провайдер: {provider_name!r}")


def judge_pair(pair: dict) -> dict:
    """Фасад для UI. НИКОГДА не бросает исключение. Инвариант §3 RULES.

    Args:
        pair: dict с ключами tender_id, catalog_id, tender_name, catalog_pn,
              catalog_mfr, match_probability (§7.0 дизайна Gate 8.2).

    Returns:
        Валидный verdict-dict (§3 дизайна) — всегда, даже при сбое.
    """
    start = time.monotonic()
    prob = float(pair.get("match_probability", 0.0))

    def _make_verdict(
        status: str,
        *,
        is_match: bool | None = None,
        confidence: str | None = None,
        reasoning: str = "",
        model: str | None = None,
        latency_ms: int | None = None,
    ) -> dict:
        disagree = status == "ok" and is_match is False and prob >= 0.75
        return {
            "status": status,
            "is_match": is_match,
            "confidence": confidence,
            "reasoning": reasoning,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "scored_at_probability": prob,
            "splink_llm_disagree": disagree,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency_ms,
        }

    try:
        if not llm_judge_config.is_enabled():
            return _make_verdict("error", reasoning="LLM-judge отключён")

        provider = get_provider()
        timeout = llm_judge_config.get_timeout()
        result = provider.judge(pair, timeout_sec=timeout)
        latency_ms = int((time.monotonic() - start) * 1000)

        return _make_verdict(
            "ok",
            is_match=result["is_match"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            model=result.get("model"),
            latency_ms=latency_ms,
        )

    except requests.exceptions.Timeout:
        latency_ms = int((time.monotonic() - start) * 1000)
        return _make_verdict("timeout", reasoning="Превышен таймаут запроса к LLM", latency_ms=latency_ms)
    except _InvalidResponseError as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return _make_verdict("invalid_response", reasoning=str(exc), latency_ms=latency_ms)
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.exception("judge_pair unhandled error: %s", exc)
        return _make_verdict("error", reasoning=str(exc), latency_ms=latency_ms)


def check_connection() -> dict:
    """OAuth-пинг для кнопки «Тест» в UI. Без chat-запроса.

    Returns:
        {"ok": bool, "error": str | None}
    """
    try:
        provider = get_provider()
        if not isinstance(provider, GigaChatProvider):
            return {"ok": False, "error": f"Провайдер {provider.name!r} не поддерживает OAuth-пинг"}
        provider._get_token()
        return {"ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _parse_json(text: str) -> dict:
    """Парсит JSON-ответ модели. Снимает markdown-фенс если есть.

    Returns:
        {"ok": True, "is_match": bool, "confidence": str, "reasoning": str}
        или {"ok": False, "error": str}
    """
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Не JSON: {exc}"}

    if not isinstance(data, dict):
        return {"ok": False, "error": "Ответ не является объектом JSON"}

    is_match = data.get("is_match")
    confidence = data.get("confidence")
    reasoning = data.get("reasoning")

    if not isinstance(is_match, bool):
        return {"ok": False, "error": f"is_match должен быть bool, получен {type(is_match).__name__}"}
    if confidence not in ("high", "medium", "low"):
        return {"ok": False, "error": f"confidence должен быть high/medium/low, получен {confidence!r}"}
    if not isinstance(reasoning, str):
        return {"ok": False, "error": f"reasoning должен быть строкой, получен {type(reasoning).__name__}"}

    return {"ok": True, "is_match": is_match, "confidence": confidence, "reasoning": reasoning}
