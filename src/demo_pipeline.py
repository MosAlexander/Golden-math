"""
demo_pipeline.py — Единая точка входа: полный пайплайн end-to-end.

Запуск:
  python -m src.demo_pipeline

Что делает:
  1. Загружает seed-каталог Radal (15 позиций)
  2. Загружает тестовые тендеры (14 штук, сценарии A/B/C)
  3. Нормализует оба потока через normalizer_electronics
  4. Запускает matching (Splink или fallback)
  5. Считает relevance score
  6. Выводит отчёт с валидацией expected_match
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .seed_catalog_radal import get_seed_catalog
from .test_tenders import get_test_tenders, TEST_TENDERS
from .splink_config import (
    prepare_catalog_for_splink,
    prepare_tenders_for_splink,
    run_matching_pipeline,
    calculate_relevance,
)
from .normalizer_electronics import normalize_catalog_item, normalize_tender_item


def run_pipeline() -> dict:
    """Запускает полный пайплайн и возвращает структурированный результат.

    Returns:
        dict with keys: timestamp, catalog, tenders, results, best_matches,
        validation, summary.
    """
    # ─────────────────────────────────────────
    # 1. Загрузка данных
    # ─────────────────────────────────────────
    catalog_raw = get_seed_catalog()
    tenders_raw = get_test_tenders()

    # ─────────────────────────────────────────
    # 2. Нормализация каталога
    # ─────────────────────────────────────────
    catalog_normalized = []
    for item in catalog_raw:
        rec = normalize_catalog_item(
            source_id=item["id"],
            name=item["name"],
            part_number=item.get("part_number", ""),
            manufacturer=item.get("manufacturer", ""),
            category=item.get("category", ""),
        )
        catalog_normalized.append(rec)

    # ─────────────────────────────────────────
    # 3. Нормализация тендеров
    # ─────────────────────────────────────────
    tender_normalized = []
    for tender in tenders_raw:
        rec = normalize_tender_item(
            source_id=tender["id"],
            name=tender["name"],
            category=tender.get("okpd2", ""),
            region=tender.get("region", ""),
            price_max=tender.get("price_max"),
            quantity_str=tender.get("quantity_str", ""),
        )
        tender_normalized.append(rec)

    # ─────────────────────────────────────────
    # 4. Подготовка для Splink
    # ─────────────────────────────────────────
    catalog_splink = prepare_catalog_for_splink(catalog_raw)
    tender_splink = prepare_tenders_for_splink(tenders_raw)

    # ─────────────────────────────────────────
    # 5. Matching
    # ─────────────────────────────────────────
    results = run_matching_pipeline(catalog_splink, tender_splink)

    # ─────────────────────────────────────────
    # 6. Relevance ranking
    # ─────────────────────────────────────────
    for match in results:
        match["relevance"] = calculate_relevance(match)
    results.sort(key=lambda x: x["relevance"], reverse=True)

    # ─────────────────────────────────────────
    # 7. Summary counts (per row, как в оригинале)
    # ─────────────────────────────────────────
    auto_count = 0
    borderline_count = 0
    reject_count = 0
    for m in results:
        decision = m["decision"]
        if decision == "auto":
            auto_count += 1
        elif decision == "borderline":
            borderline_count += 1
        else:
            reject_count += 1

    # ─────────────────────────────────────────
    # 8. Best matches per tender
    # ─────────────────────────────────────────
    best_matches: dict[str, list] = {}
    for m in results:
        tid = m["tender_id"]
        if tid not in best_matches or m["match_probability"] > best_matches[tid][1]:
            best_matches[tid] = [m["catalog_id"], m["match_probability"]]

    # ─────────────────────────────────────────
    # 9. Validation
    # ─────────────────────────────────────────
    correct = 0
    missed = 0
    total_validated = 0
    validation_details = []

    for tender in tenders_raw:
        tid = tender["id"]
        expected = tender.get("expected_match", "")
        if not expected:
            continue

        total_validated += 1
        expected_ids = set(expected.split(","))

        if tid in best_matches:
            actual_id, actual_score = best_matches[tid]
            ok = actual_id in expected_ids
            if ok:
                correct += 1
            else:
                missed += 1
            validation_details.append({
                "tender_id": tid,
                "expected": expected,
                "actual": actual_id,
                "score": actual_score,
                "ok": ok,
            })
        else:
            missed += 1
            validation_details.append({
                "tender_id": tid,
                "expected": expected,
                "actual": None,
                "score": 0.0,
                "ok": False,
            })

    return {
        "timestamp": datetime.now().isoformat(),
        "catalog": catalog_raw,
        "tenders": tenders_raw,
        "results": results,
        "best_matches": best_matches,
        "validation": {
            "correct": correct,
            "missed": missed,
            "total": total_validated,
            "details": validation_details,
        },
        "summary": {
            "auto": auto_count,
            "borderline": borderline_count,
            "reject": reject_count,
        },
        "_normalized": {
            "catalog": catalog_normalized,
            "tenders": tender_normalized,
        },
        "_splink": {
            "catalog": catalog_splink,
            "tender": tender_splink,
        },
    }


def _print_report(result: dict) -> None:
    """Выводит полный отчёт пайплайна в stdout.

    Args:
        result: dict, returned by run_pipeline().
    """
    catalog_raw = result["catalog"]
    tenders_raw = result["tenders"]
    results = result["results"]
    catalog_normalized = result["_normalized"]["catalog"]
    tender_normalized = result["_normalized"]["tenders"]
    catalog_splink = result["_splink"]["catalog"]
    tender_splink = result["_splink"]["tender"]
    auto_count = result["summary"]["auto"]
    borderline_count = result["summary"]["borderline"]
    reject_count = result["summary"]["reject"]
    best_matches = result["best_matches"]
    validation = result["validation"]
    correct = validation["correct"]
    missed = validation["missed"]
    total_validated = validation["total"]

    print()
    print("▀" * 64)
    print("  GoldenMatch Pro — Full Pipeline Demo (Radal)")
    print("▀" * 64)

    # ─────────────────────────────────────────
    # 1. Загрузка данных
    # ─────────────────────────────────────────
    print("\n▶ Step 1: Loading data...")
    print(f"  Catalog: {len(catalog_raw)} items")
    print(f"  Tenders: {len(tenders_raw)} items")

    # ─────────────────────────────────────────
    # 2. Нормализация каталога
    # ─────────────────────────────────────────
    print("\n▶ Step 2: Normalizing catalog...")
    for rec in catalog_normalized:
        print(f"  {rec.source_id:8s} | PN: {rec.part_number_primary:24s} | "
              f"MFR: {rec.manufacturer:22s} | Cat: {rec.category}")

    # ─────────────────────────────────────────
    # 3. Нормализация тендеров
    # ─────────────────────────────────────────
    print("\n▶ Step 3: Normalizing tenders...")
    for rec in tender_normalized:
        scenario = rec.match_scenario
        print(f"  {rec.source_id:8s} [{scenario}] | PN: {rec.part_number_primary or '—':24s} | "
              f"MFR: {rec.manufacturer or '—':22s} | Cat: {rec.category or '—'}")

    # ─────────────────────────────────────────
    # 4. Подготовка для Splink
    # ─────────────────────────────────────────
    print("\n▶ Step 4: Preparing data for matching engine...")
    print(f"  Catalog rows: {len(catalog_splink)}")
    print(f"  Tender rows:  {len(tender_splink)}")

    # ─────────────────────────────────────────
    # 5. Matching
    # ─────────────────────────────────────────
    print("\n▶ Step 5: Running matching pipeline...")
    print(f"  Raw matches found: {len(results)}")

    # ─────────────────────────────────────────
    # 6. Relevance ranking
    # ─────────────────────────────────────────
    print("\n▶ Step 6: Calculating relevance scores...")

    # ─────────────────────────────────────────
    # 7. Отчёт
    # ─────────────────────────────────────────
    print("\n" + "═" * 110)
    print("  RESULTS (sorted by relevance)")
    print("═" * 110)
    print(f"  {'Tender':<10} {'Catalog PN':<26} {'MFR':<20} "
          f"{'Match':<8} {'Decision':<14} {'Stock':<8} {'NMC':<10} {'Relevance':<10}")
    print("  " + "─" * 104)

    for m in results:
        decision = m["decision"]
        if decision == "auto":
            icon = "✓"
        elif decision == "borderline":
            icon = "?"
        else:
            icon = "✗"

        stock_str = f"{m['stock_qty']} шт" if m.get("in_stock") else "—"
        nmc_str = _format_nmc(m.get("price_max", 0))

        print(
            f"  {icon} {m['tender_id']:<8} {m['catalog_pn']:<26} "
            f"{m['catalog_mfr']:<20} {m['match_probability']:.2f}    "
            f"{decision:<14} {stock_str:<8} {nmc_str:<10} {m['relevance']:.3f}"
        )

    # ─────────────────────────────────────────
    # 8. Summary
    # ─────────────────────────────────────────
    print()
    print("═" * 110)
    print("  SUMMARY")
    print("═" * 110)
    print(f"  Auto-match (≥0.92):     {auto_count}")
    print(f"  Borderline → LLM-judge: {borderline_count}")
    print(f"  Rejected (<0.75):       {reject_count}")
    print(f"  Total relevant:         {auto_count + borderline_count}")
    print()

    # ─────────────────────────────────────────
    # 9. Validation against expected_match
    # ─────────────────────────────────────────
    print("═" * 110)
    print("  VALIDATION (expected_match check)")
    print("═" * 110)

    for detail in validation["details"]:
        tid = detail["tender_id"]
        expected = detail["expected"]
        actual = detail["actual"]
        score = detail["score"]
        ok = detail["ok"]

        if actual is not None:
            if ok:
                print(f"  ✓ {tid}: expected {expected}, got {actual} (score {score:.2f})")
            else:
                print(f"  ✗ {tid}: expected {expected}, got {actual} (score {score:.2f})")
        else:
            print(f"  ✗ {tid}: expected {expected}, got NO MATCH")

    print()
    if total_validated > 0:
        accuracy = correct / total_validated * 100
        print(f"  Accuracy: {correct}/{total_validated} = {accuracy:.1f}%")
        print(f"  Missed:   {missed}/{total_validated}")
    else:
        print("  No tenders with expected_match to validate.")

    print()
    print("─" * 64)
    print("  Pipeline complete. Next steps:")
    print("  1. pip install splink duckdb → replace fallback with real Splink")
    print("  2. Connect TenderGuru API → real tender feed")
    print("  3. Get Radal catalog CSV → replace seed_catalog")
    print("  4. Launch Streamlit dashboard")
    print("─" * 64)
    print()


def main():
    import sys
    # Принудительно UTF-8 для stdout/stderr — иначе на Windows
    # при subprocess/pipe/редиректе падаем с UnicodeEncodeError на
    # символах вроде ✓ ✗ ▶ ═ → ₽ внутри _print_report().
    # reconfigure() появилась в Python 3.7, у нас 3.11+.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stderr,
    )
    result = run_pipeline()
    _print_report(result)

    correct = result["validation"]["correct"]
    total = result["validation"]["total"]
    accuracy_str = f"{correct}/{total}"

    cache_data = {
        "timestamp": result["timestamp"],
        "accuracy": accuracy_str,
        "results": result["results"],
        "catalog": result["catalog"],
        "tenders": [
            {
                **t,
                "best_match_id": result["best_matches"].get(t["id"], [None, 0.0])[0],
                "best_match_score": result["best_matches"].get(t["id"], [None, 0.0])[1],
            }
            for t in result["tenders"]
        ],
    }

    Path("data").mkdir(exist_ok=True)
    Path("data/last_run.json").write_text(
        json.dumps(cache_data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    with open("docs/pipeline_runs.log", "a", encoding="utf-8") as f:
        f.write(
            f"{result['timestamp']} | "
            f"accuracy={accuracy_str} | "
            f"matches={len(result['results'])} | "
            f"runtime=fallback\n"
        )


def _format_nmc(val):
    if not val:
        return "—"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M ₽"
    if val >= 1_000:
        return f"{val / 1_000:.0f}K ₽"
    return f"{val:.0f} ₽"


if __name__ == "__main__":
    main()
