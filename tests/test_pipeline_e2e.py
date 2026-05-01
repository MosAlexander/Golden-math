"""
test_pipeline_e2e.py — Архитектурные инварианты пайплайна.

Эти три теста — НЕ юниты. Они проверяют поведенческие контракты
продукта, которые должны выполняться при любом движке matching
(fallback, Splink, будущие версии).

Инварианты:
  1. Happy path: тендер с точным PN, который есть в каталоге,
     попадает в auto-decision.
  2. Garbage rejection: тендер без связи с каталогом не попадает
     в auto ни при каком движке.
  3. Parametric isolation: тендер сценария B (без PN) не попадает
     в auto — обязан пройти LLM-judge через borderline.

Запрещено привязывать к точным probability/счёту матчей —
тесты должны выдержать смену движка без правок. См. RULES.md §7.
"""
from __future__ import annotations

import pytest

from src.demo_pipeline import run_pipeline


@pytest.fixture(scope="module")
def pipeline_result():
    """Прогон полного пайплайна один раз на весь модуль.

    scope='module' — экономит время: pipeline отрабатывает 0.7 сек,
    а тестов три, и им нужны те же самые results.
    """
    return run_pipeline()


# ══════════════════════════════════════════════
# ИНВАРИАНТ 1: Happy path
# ══════════════════════════════════════════════

def test_happy_path_exact_pn_routes_to_auto(pipeline_result):
    """Тендер с точным PN из каталога должен матчиться в auto без LLM.

    T-A01 содержит "CM1000E3U-34NF Mitsubishi" — точно тот PN, который
    есть в каталоге Radal как RAD-001. Это базовое обещание продукта
    Сценария A: если PN явно указан и SKU есть в каталоге — auto-match.

    Этот инвариант защищает контракт продукта на всех последующих этапах:
    - Gate 4: добавление кэша не должно сломать структуру results
    - Gate 8: LLM-интеграция не должна перехватывать auto-матчи
    - Gate 9: переход на Splink должен сохранить exact-PN-matching
    """
    matching_pairs = [
        r for r in pipeline_result["results"]
        if r["tender_id"] == "T-A01"
        and r["catalog_id"] == "RAD-001"
        and r["decision"] == "auto"
    ]
    assert len(matching_pairs) >= 1, (
        "Контракт продукта нарушен: тендер T-A01 (CM1000E3U-34NF Mitsubishi) "
        "не нашёл RAD-001 в auto-decision. Это базовое обещание Сценария A."
    )


# ══════════════════════════════════════════════
# ИНВАРИАНТ 2: Garbage rejection (precision > recall)
# ══════════════════════════════════════════════

def test_garbage_tender_never_routes_to_auto():
    """Несвязанный с электроникой тендер не должен генерировать auto-матчи.

    Бизнес-обещание: система не шлёт ложные алерты в Telegram. Если
    мусорный тендер пройдёт через все слои и вылезет как auto-match —
    это потеря доверия клиента. RULES.md §2: precision > recall.

    Используем синтетический тендер про офисную бумагу — заведомо нет
    общего ни с одной позицией каталога Radal (IGBT, ПЛИС, тиристоры).
    """
    from src.splink_config import (
        prepare_catalog_for_splink,
        prepare_tenders_for_splink,
        run_matching_pipeline,
    )
    from src.seed_catalog_radal import get_seed_catalog

    garbage_tender = [{
        "id": "T-GARBAGE-001",
        "name": "Поставка офисной бумаги формата А4 80 г/м² 500 листов",
        "okpd2": "17.23",
        "region": "Москва",
        "price_max": 50_000.0,
        "quantity_str": "100 уп",
        "deadline_days": 30,
    }]

    catalog = prepare_catalog_for_splink(get_seed_catalog())
    tenders = prepare_tenders_for_splink(garbage_tender)
    results = run_matching_pipeline(catalog, tenders)

    auto_matches = [r for r in results if r["decision"] == "auto"]
    assert auto_matches == [], (
        f"Контракт продукта нарушен: precision > recall. Мусорный тендер "
        f"(офисная бумага) сгенерировал {len(auto_matches)} auto-матча(ей) "
        f"с каталогом электронных компонентов. "
        f"Ложные auto-алерты недопустимы. См. RULES.md §2."
    )


# ══════════════════════════════════════════════
# ИНВАРИАНТ 3: Parametric isolation (Сценарий B → borderline, не auto)
# ══════════════════════════════════════════════

def test_parametric_match_never_routes_to_auto(pipeline_result):
    """Параметрический матч (Сценарий B, без PN) не должен попадать в auto.

    Архитектурный контракт: матч только по категории+параметрам, без
    подтверждения через part number, обязан проходить через LLM-judge
    как borderline. Прямой проход в auto без LLM — нарушение трёх правил
    одновременно:
      - RULES.md §1: нельзя принимать решение только по описанию без PN
      - RULES.md §3: LLM-judge только для borderline, не для auto
      - DECISIONS.md §3: scenario router B → парам. matching, не exact

    T-B01 — "IGBT-модули 600В 75А" — нет PN в тексте, есть только
    параметры. На текущем fallback он не матчится вовсе (auto-матчей
    просто нет — инвариант истинен). На будущем Splink он, вероятно,
    будет давать borderline (auto-матчей всё равно нет — инвариант
    остаётся истинен). Если когда-то Splink или LLM начнёт давать ему
    auto — этот тест поймает регрессию.
    """
    t_b01_pairs = [
        r for r in pipeline_result["results"]
        if r["tender_id"] == "T-B01"
    ]
    auto_pairs = [r for r in t_b01_pairs if r["decision"] == "auto"]

    assert auto_pairs == [], (
        f"Архитектурный контракт нарушен: параметрический матч (Сценарий B, "
        f"без PN) попал в {len(auto_pairs)} auto-decision(ах) в обход "
        f"LLM-judge. Тендер T-B01 не содержит part number — auto-матч "
        f"без LLM-подтверждения недопустим. См. RULES.md §1, §3."
    )
