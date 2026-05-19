"""
splink_config.py — Конфигурация Splink для cross-matching тендеров с каталогом Radal.

Splink использует модель Fellegi-Sunter: для каждой пары записей (тендер, каталог)
считается вероятность, что они описывают один и тот же товар.

Ключевые настройки:
  1. Blocking rules — как группировать записи (чтобы не сравнивать всё со всем)
  2. Comparison levels — как сравнивать каждое поле (exact / fuzzy / null)
  3. Weights — автоматически обучаются Splink (EM-алгоритм)
  4. Thresholds — пороги для авто-матча и borderline

Запуск:
  pip install splink duckdb
  python -m normalizer_electronics.splink_config
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
# 1. ПОДГОТОВКА ДАННЫХ ДЛЯ SPLINK
# ══════════════════════════════════════════════

def prepare_catalog_for_splink(seed_catalog: list[dict]) -> list[dict]:
    """
    Превращает seed-каталог в формат, понятный Splink.

    Splink работает с плоскими записями (dict → DataFrame).
    Каждая запись = одна строка с полями для сравнения.
    """
    rows = []
    for item in seed_catalog:
        rows.append({
            "unique_id": item["id"],
            "source": "catalog",
            "part_number": item["part_number"].upper().replace(" ", ""),
            "pn_prefix": item["part_number"].upper()[:6],  # для blocking
            "manufacturer": item.get("manufacturer", "").lower(),
            "category": item.get("category", ""),
            "voltage_v": item.get("params", {}).get("voltage_v"),
            "current_a": item.get("params", {}).get("current_a"),
            "package": item.get("params", {}).get("package", ""),
            "name_clean": item["name"].lower(),
            "in_stock": item.get("in_stock", False),
            "stock_qty": item.get("stock_qty", 0),
        })
    return rows


def prepare_tenders_for_splink(test_tenders: list[dict]) -> list[dict]:
    """
    Превращает тендеры в формат Splink после нормализации.

    В production это вызывается после normalizer_electronics.normalize_tender_item().
    Здесь — упрощённая версия для seed-данных.
    """
    from .normalizer_electronics import normalize_tender_item

    rows = []
    for tender in test_tenders:
        rec = normalize_tender_item(
            source_id=tender["id"],
            name=tender["name"],
            category=tender.get("okpd2", ""),
            region=tender.get("region", ""),
            price_max=tender.get("price_max"),
            quantity_str=tender.get("quantity_str", ""),
        )

        rows.append({
            "unique_id": rec.source_id,
            "source": "tender",
            "part_number": rec.part_number_primary,
            "pn_prefix": rec.part_number_primary[:6] if rec.part_number_primary else "",
            "manufacturer": rec.manufacturer.lower() if rec.manufacturer else "",
            "category": rec.category,
            "voltage_v": rec.params.get("voltage_v"),
            "current_a": rec.params.get("current_a"),
            "package": rec.params.get("package", ""),
            "name_clean": rec.name_clean,
            # Тендерные поля (не участвуют в matching, но нужны для ranking)
            "region": rec.region,
            "price_max": rec.price_max,
            "quantity": rec.quantity,
            "deadline_days": tender.get("deadline_days"),
        })
    return rows


# ══════════════════════════════════════════════
# 2. SPLINK SETTINGS (модель Fellegi-Sunter)
# ══════════════════════════════════════════════

def get_splink_settings() -> dict:
    """
    Возвращает настройки для Splink Linker.

    Это конфигурация модели: какие поля сравнивать и как.
    Веса обучаются автоматически через EM-алгоритм.
    """
    return {
        # Уникальный ID записи
        "unique_id_column_name": "unique_id",

        # Столбец, отличающий таблицы (для link-only, без дедупликации)
        "source_dataset_column_name": "source",

        # Поля сравнения с уровнями (от сильного к слабому)
        "comparisons": [
            # ─── Part Number (главное поле, вес ~60%) ───
            # Уровни:
            #   1. Exact match (CM1000E3U-34NF == CM1000E3U-34NF) → сильнейший сигнал
            #   2. Содержит (один PN содержит другой) → частичный матч
            #   3. Все остальное → не совпало
            {
                "output_column_name": "part_number",
                "comparison_levels": [
                    {
                        "sql_condition": "part_number_l = part_number_r",
                        "label_for_charts": "Exact PN match",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": (
                            "part_number_l LIKE '%' || part_number_r || '%' "
                            "OR part_number_r LIKE '%' || part_number_l || '%'"
                        ),
                        "label_for_charts": "Partial PN match",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": "ELSE",
                        "label_for_charts": "No PN match",
                    },
                ],
                "comparison_description": "Part number comparison",
            },

            # ─── Manufacturer (вес ~20%) ───
            {
                "output_column_name": "manufacturer",
                "comparison_levels": [
                    {
                        "sql_condition": "manufacturer_l = manufacturer_r",
                        "label_for_charts": "Exact manufacturer",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": "ELSE",
                        "label_for_charts": "Different manufacturer",
                    },
                ],
                "comparison_description": "Manufacturer comparison",
            },

            # ─── Category (вес ~8%) ───
            {
                "output_column_name": "category",
                "comparison_levels": [
                    {
                        "sql_condition": "category_l = category_r",
                        "label_for_charts": "Same category",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": "ELSE",
                        "label_for_charts": "Different category",
                    },
                ],
                "comparison_description": "Component category",
            },

            # ─── Voltage (вес ~4%) ───
            {
                "output_column_name": "voltage_v",
                "comparison_levels": [
                    {
                        "sql_condition": "voltage_v_l = voltage_v_r",
                        "label_for_charts": "Exact voltage",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": (
                            "ABS(voltage_v_l - voltage_v_r) / "
                            "GREATEST(voltage_v_l, voltage_v_r, 1) < 0.1"
                        ),
                        "label_for_charts": "Voltage within 10%",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": "ELSE",
                        "label_for_charts": "Different voltage",
                    },
                ],
                "comparison_description": "Voltage comparison",
            },

            # ─── Current (вес ~4%) ───
            {
                "output_column_name": "current_a",
                "comparison_levels": [
                    {
                        "sql_condition": "current_a_l = current_a_r",
                        "label_for_charts": "Exact current",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": (
                            "ABS(current_a_l - current_a_r) / "
                            "GREATEST(current_a_l, current_a_r, 1) < 0.15"
                        ),
                        "label_for_charts": "Current within 15%",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": "ELSE",
                        "label_for_charts": "Different current",
                    },
                ],
                "comparison_description": "Current comparison",
            },

            # ─── Description fuzzy (вес ~4%) ───
            {
                "output_column_name": "name_clean",
                "comparison_levels": [
                    {
                        "sql_condition": "name_clean_l = name_clean_r",
                        "label_for_charts": "Exact name",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": (
                            "jaro_winkler_similarity(name_clean_l, name_clean_r) > 0.88"
                        ),
                        "label_for_charts": "Similar name (JW > 0.88)",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": (
                            "jaro_winkler_similarity(name_clean_l, name_clean_r) > 0.7"
                        ),
                        "label_for_charts": "Somewhat similar (JW > 0.7)",
                        "is_null_level": False,
                    },
                    {
                        "sql_condition": "ELSE",
                        "label_for_charts": "Different name",
                    },
                ],
                "comparison_description": "Description fuzzy match",
            },
        ],

        # Blocking rules (какие пары вообще сравниваем)
        "blocking_rules_to_generate_predictions": [
            # Правило 1: совпадение по prefix PN (первые 6 символов)
            #   CM1000... ↔ CM1000... — сравниваем
            #   CM1000... ↔ 7MBR75... — пропускаем
            "l.pn_prefix = r.pn_prefix",

            # Правило 2: совпадение по (category, manufacturer)
            #   (igbt, mitsubishi) ↔ (igbt, mitsubishi) — сравниваем
            #   Покрывает сценарий B (тендер без PN, но с категорией)
            "l.category = r.category AND l.manufacturer = r.manufacturer",

            # Правило 3: совпадение по category + voltage
            #   Покрывает сценарий B без manufacturer
            "l.category = r.category AND l.voltage_v = r.voltage_v",

            # Правило 4: только category (для сценария C)
            #   Широкий матч, но фильтруется scoring'ом
            "l.category = r.category",
        ],

        # Настройки EM-алгоритма
        "max_iterations": 25,
        "em_convergence": 0.0001,

        # Порог вероятности для предсказаний
        "retain_matching_columns": True,
        "retain_intermediate_calculation_columns": True,
    }


# ══════════════════════════════════════════════
# 3. THRESHOLDS (пороги решений)
# ══════════════════════════════════════════════

# Splink выдаёт match_weight (log2 odds) и match_probability (0..1).
# Пороги задаём по probability:

THRESHOLD_AUTO_MATCH = 0.92     # ≥ 0.92 → автоматический матч, без LLM
THRESHOLD_BORDERLINE_HIGH = 0.92  # < 0.92 и ≥ 0.75 → LLM-judge
THRESHOLD_BORDERLINE_LOW = 0.75
THRESHOLD_REJECT = 0.75         # < 0.75 → отброс (не матч)

# ── Score weights ──────────────────────────────────────────────────────────────
# Веса факторов в _calculate_score(). Сумма базовых весов = 100%,
# плюс PN+MFR бонус 5% дают максимум 105% — это намеренно:
# награда за полное совпадение PN и производителя одновременно.
WEIGHT_PN_EXACT       = 0.60   # PN полностью совпадает
WEIGHT_PN_PARTIAL     = 0.40   # один PN — подстрока другого
WEIGHT_MFR            = 0.20   # производитель совпал
WEIGHT_PN_MFR_BONUS   = 0.05   # бонус за PN+MFR одновременно
WEIGHT_CATEGORY       = 0.08   # категория совпала
WEIGHT_VOLTAGE_EXACT  = 0.04   # напряжение точно совпало
WEIGHT_VOLTAGE_CLOSE  = 0.02   # напряжение в пределах 10%
WEIGHT_CURRENT_EXACT  = 0.04   # ток точно совпал
WEIGHT_CURRENT_CLOSE  = 0.02   # ток в пределах 15%
WEIGHT_DESCRIPTION    = 0.04   # коэф. при overlap слов в описании


def classify_match(probability: float) -> str:
    """
    Классифицирует результат Splink:
      "auto"      — авто-матч, отправляем в дашборд
      "borderline" — LLM-judge решает
      "reject"    — не матч
    """
    if probability >= THRESHOLD_AUTO_MATCH:
        return "auto"
    elif probability >= THRESHOLD_BORDERLINE_LOW:
        return "borderline"
    else:
        return "reject"


# ══════════════════════════════════════════════
# 4. ПОЛНЫЙ ПАЙПЛАЙН (Splink + classification)
# ══════════════════════════════════════════════

def run_matching_pipeline(catalog_data: list[dict], tender_data: list[dict]):
    """
    Полный пайплайн матчинга.

    В production:
      1. Подготовка данных
      2. Splink linking
      3. Классификация результатов
      4. LLM-judge для borderline
      5. Relevance ranking
      6. → Dashboard / Telegram

    Здесь — демо-версия без установленного Splink.
    """
    try:
        import splink
        return _run_with_splink(catalog_data, tender_data)
    except ImportError:
        logger.warning("Splink not installed, using fallback scoring")
        return _run_fallback_scoring(catalog_data, tender_data)


def _run_with_splink(catalog_data: list[dict], tender_data: list[dict]):
    """Production path: Splink."""
    from splink import Linker, DuckDBAPI, SettingsCreator
    import splink.comparison_level_library as cll
    import splink.comparison_library as cl

    db_api = DuckDBAPI()

    settings = SettingsCreator(
        link_type="link_only",
        unique_id_column_name="unique_id",
        comparisons=[
            cl.ExactMatch("part_number").configure(
                term_frequency_adjustments=True
            ),
            cl.ExactMatch("manufacturer"),
            cl.ExactMatch("category"),
            cl.ExactMatch("voltage_v"),
            cl.ExactMatch("current_a"),
            cl.JaroWinklerAtThresholds("name_clean", [0.88, 0.7]),
        ],
        blocking_rules_to_generate_predictions=[
            "l.pn_prefix = r.pn_prefix",
            "l.category = r.category AND l.manufacturer = r.manufacturer",
            "l.category = r.category AND l.voltage_v = r.voltage_v",
            "l.category = r.category",
        ],
    )

    linker = Linker(
        [catalog_data, tender_data],
        settings,
        db_api=db_api,
    )

    # Обучение модели (unsupervised EM)
    linker.training.estimate_u_using_random_sampling(max_pairs=5000)
    linker.training.estimate_parameters_using_expectation_maximisation(
        "l.part_number = r.part_number", fix_u_probabilities=False
    )
    linker.training.estimate_parameters_using_expectation_maximisation(
        "l.manufacturer = r.manufacturer", fix_u_probabilities=False
    )

    # Предсказания
    results = linker.inference.predict(threshold_match_probability=0.5)
    df = results.as_pandas_dataframe()

    # Классификация
    df["decision"] = df["match_probability"].apply(classify_match)

    return df


def _run_fallback_scoring(catalog_data: list[dict], tender_data: list[dict]):
    """
    Fallback без Splink: ручной scoring.
    Имитирует логику Splink для демонстрации пайплайна.
    """
    results = []

    for tender in tender_data:
        for catalog in catalog_data:
            score = _calculate_score(tender, catalog)
            if score > 0.3:  # минимальный порог для включения
                results.append({
                    "tender_id": tender["unique_id"],
                    "catalog_id": catalog["unique_id"],
                    "tender_name": tender.get("name_clean", "")[:60],
                    "catalog_pn": catalog["part_number"],
                    "catalog_mfr": catalog["manufacturer"],
                    "match_probability": score,
                    "decision": classify_match(score),
                    "in_stock": catalog.get("in_stock", False),
                    "stock_qty": catalog.get("stock_qty", 0),
                    # Для ranking
                    "price_max": tender.get("price_max"),
                    "deadline_days": tender.get("deadline_days"),
                    "region": tender.get("region", ""),
                })

    # Сортируем по вероятности (лучшие матчи сверху)
    results.sort(key=lambda x: x["match_probability"], reverse=True)
    return results


def _calculate_score(tender: dict, catalog: dict) -> float:
    """Ручной scoring, имитирующий веса Splink."""
    score = 0.0

    # Part number exact (60%)
    t_pn = tender.get("part_number", "")
    c_pn = catalog.get("part_number", "")
    if t_pn and c_pn:
        if t_pn == c_pn:
            score += WEIGHT_PN_EXACT
        elif t_pn in c_pn or c_pn in t_pn:
            score += WEIGHT_PN_PARTIAL

    # Manufacturer (20%)
    t_mfr = tender.get("manufacturer", "")
    c_mfr = catalog.get("manufacturer", "")
    if t_mfr and c_mfr and t_mfr == c_mfr:
        score += WEIGHT_MFR

    # PN+MFR sufficiency bonus (RULES.md §1: точный PN+MFR → auto)
    # Архитектурный контракт: при точном совпадении part number и
    # manufacturer матч обязан попадать в auto-decision независимо
    # от наличия параметров в тендере (см. DECISIONS.md).
    # Без этого Сценарий A с короткими тендерными текстами теряет
    # auto-классификацию из-за отсутствия voltage/current в тексте.
    if t_pn and c_pn and t_pn == c_pn and t_mfr and c_mfr and t_mfr == c_mfr:
        score += WEIGHT_PN_MFR_BONUS

    # Category (8%)
    if tender.get("category") and catalog.get("category"):
        if tender["category"] == catalog["category"]:
            score += WEIGHT_CATEGORY

    # Voltage (4%)
    t_v = tender.get("voltage_v")
    c_v = catalog.get("voltage_v")
    if t_v and c_v:
        if t_v == c_v:
            score += WEIGHT_VOLTAGE_EXACT
        elif abs(t_v - c_v) / max(t_v, c_v, 1) < 0.1:
            score += WEIGHT_VOLTAGE_CLOSE

    # Current (4%)
    t_a = tender.get("current_a")
    c_a = catalog.get("current_a")
    if t_a and c_a:
        if t_a == c_a:
            score += WEIGHT_CURRENT_EXACT
        elif abs(t_a - c_a) / max(t_a, c_a, 1) < 0.15:
            score += WEIGHT_CURRENT_CLOSE

    # Name fuzzy (4%) — simplified JW
    t_name = tender.get("name_clean", "")
    c_name = catalog.get("name_clean", "")
    if t_name and c_name:
        # Простая метрика: доля общих слов
        t_words = set(t_name.split())
        c_words = set(c_name.split())
        if t_words and c_words:
            overlap = len(t_words & c_words) / max(len(t_words), len(c_words))
            score += WEIGHT_DESCRIPTION * overlap

    return min(score, 1.0)


# ══════════════════════════════════════════════
# 5. RELEVANCE RANKING (после matching)
# ══════════════════════════════════════════════

def calculate_relevance(match: dict) -> float:
    """
    Итоговый relevance score для приоритизации в дашборде.

    Formula:
      match quality (40%) + stock availability (25%) +
      margin estimate (20%) + deadline urgency (15%)
    """
    # Match quality (0..1) → 40%
    mq = match.get("match_probability", 0) * 0.40

    # Stock availability → 25%
    if match.get("in_stock") and match.get("stock_qty", 0) > 0:
        stock_score = min(match["stock_qty"] / 50, 1.0)  # normalize to 0..1
        sa = stock_score * 0.25
    else:
        sa = 0.0

    # Margin estimate (по НМЦ тендера) → 20%
    price = match.get("price_max", 0)
    if price and price > 100_000:
        me = 0.20  # высокая НМЦ → потенциально высокая маржа
    elif price and price > 50_000:
        me = 0.12
    else:
        me = 0.05

    # Deadline urgency → 15%
    days = match.get("deadline_days", 30)
    if days <= 5:
        du = 0.15  # срочно
    elif days <= 10:
        du = 0.10
    elif days <= 20:
        du = 0.05
    else:
        du = 0.02

    return mq + sa + me + du


# ══════════════════════════════════════════════
# MAIN: демо полного пайплайна
# ══════════════════════════════════════════════

def main():
    from .seed_catalog_radal import get_seed_catalog
    from .test_tenders import get_test_tenders

    print("\n" + "▀" * 60)
    print("  GoldenMatch Pro — Full Pipeline Demo (Radal)")
    print("▀" * 60)

    # 1. Подготовка данных
    print("\n▶ Preparing data...")
    catalog = prepare_catalog_for_splink(get_seed_catalog())
    tenders = prepare_tenders_for_splink(get_test_tenders())
    print(f"  Catalog: {len(catalog)} items")
    print(f"  Tenders: {len(tenders)} items")

    # 2. Matching
    print("\n▶ Running matching pipeline...")
    results = run_matching_pipeline(catalog, tenders)

    # 3. Relevance ranking
    print("\n▶ Calculating relevance scores...")
    for match in results:
        match["relevance"] = calculate_relevance(match)
    results.sort(key=lambda x: x["relevance"], reverse=True)

    # 4. Отчёт
    print("\n▶ RESULTS (sorted by relevance)\n")
    print(f"  {'Tender':<10} {'Catalog PN':<24} {'MFR':<18} "
          f"{'Match':<8} {'Decision':<12} {'Stock':<8} {'Relevance':<10}")
    print("  " + "─" * 98)

    auto = borderline = reject = 0
    for m in results:
        decision = m["decision"]
        if decision == "auto":
            auto += 1
            icon = "✓"
        elif decision == "borderline":
            borderline += 1
            icon = "?"
        else:
            reject += 1
            icon = "✗"

        stock = f"{m['stock_qty']} шт" if m["in_stock"] else "—"
        print(
            f"  {icon} {m['tender_id']:<8} {m['catalog_pn']:<24} "
            f"{m['catalog_mfr']:<18} {m['match_probability']:.2f}    "
            f"{decision:<12} {stock:<8} {m['relevance']:.3f}"
        )

    print(f"\n  Summary: {auto} auto-match, {borderline} borderline → LLM, "
          f"{reject} rejected")
    print(f"  Total relevant matches: {auto + borderline}")


if __name__ == "__main__":
    main()
