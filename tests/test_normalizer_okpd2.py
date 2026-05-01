"""Регрессионный тест на disentanglement okpd2 vs taxonomy.

Контракт: normalize_tender_item принимает в параметре category либо
строку из нашей таксономии (igbt, thyristor, ...), либо okpd2-код
(26.11.12). Они должны жить в РАЗНЫХ полях:
  - category   → таксономия (или результат detect_category)
  - extra.okpd2 → okpd2-код (если был передан)
"""
from src.normalizer_electronics import normalize_tender_item


def test_normalize_tender_okpd2_goes_to_extra():
    """okpd2-код не подменяет category, а уходит в extra.okpd2."""
    rec = normalize_tender_item(
        source_id="okpd-test-1",
        name="Поставка IGBT-модулей CM1000E3U-34NF Mitsubishi",
        category="26.11.12",  # это okpd2, не таксономия
    )
    # category должна быть определена из текста через detect_category
    assert rec.category == "igbt", (
        f"Ожидали category='igbt' (из detect_category), получили "
        f"'{rec.category}'. okpd2 не должен подменять таксономию."
    )
    # okpd2 сохранён в extra
    assert rec.extra.get("okpd2") == "26.11.12", (
        f"okpd2-код должен быть сохранён в extra.okpd2, получили: "
        f"{rec.extra}"
    )


def test_normalize_tender_taxonomy_passed_through():
    """Если передаём таксономию напрямую — она остаётся как есть."""
    rec = normalize_tender_item(
        source_id="tax-test-1",
        name="IGBT module CM1000E3U-34NF",
        category="igbt",  # наша таксономия
    )
    assert rec.category == "igbt"
    # okpd2 в extra появиться не должно (мы его не передавали)
    assert "okpd2" not in rec.extra or rec.extra.get("okpd2") == ""


def test_normalize_tender_no_category_uses_detect():
    """Если category не передана — берётся detect_category из текста."""
    rec = normalize_tender_item(
        source_id="detect-test-1",
        name="Поставка тиристорного модуля SKKT162-16E SEMIKRON",
    )
    # Должно быть определено из слова "тиристорного"
    assert rec.category == "thyristor"
    assert "okpd2" not in rec.extra or rec.extra.get("okpd2") == ""


def test_pn_mfr_sufficiency_bonus_pushes_to_auto():
    """T-A01 ↔ RAD-001 должен получать decision='auto' после фиксов.

    Это интеграционный тест на оба фикса вместе:
    - okpd2 disentanglement → category совпадёт (igbt vs igbt, не 26.11.12)
    - sufficiency bonus → +0.05 при точном PN+MFR
    Итого: 0.81 + 0.08 (category) + 0.05 (bonus) = ~0.94 → auto.
    """
    from src.demo_pipeline import run_pipeline
    result = run_pipeline()
    pair = next(
        (r for r in result["results"]
         if r["tender_id"] == "T-A01" and r["catalog_id"] == "RAD-001"),
        None,
    )
    assert pair is not None, "T-A01 должен матчить RAD-001"
    assert pair["decision"] == "auto", (
        f"После фиксов T-A01 ↔ RAD-001 должен быть в auto. "
        f"Получили decision='{pair['decision']}', "
        f"probability={pair.get('match_probability')}"
    )
