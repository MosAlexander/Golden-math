"""
normalizer_electronics.py — Пайплайн нормализации для микроэлектроники.

Ключевое отличие от промышленной номенклатуры:
  → Part number = главный ключ матчинга (exact/near-exact)
  → Manufacturer = второй ключ
  → Категория + параметры = третий уровень (для тендеров без part number)

Три сценария матчинга тендера с каталогом Radal:

  Сценарий A (70% тендеров):
    Тендер содержит part number → exact match по нормализованному PN
    Пример: "Поставка IGBT CM1000E3U-34NF Mitsubishi" → PN: CM1000E3U-34NF

  Сценарий B (20% тендеров):
    Тендер содержит описание + параметры → параметрический матчинг
    Пример: "IGBT-модуль 1200В 400А Mitsubishi" → категория + параметры + производитель

  Сценарий C (10% тендеров):
    Общее описание → категорийный матчинг
    Пример: "Поставка электронных компонентов для АСУТП" → широкая категория
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .domain_dict_electronics import (
    normalize_part_number,
    find_manufacturer,
    detect_category,
    extract_electrical_params,
    RE_PART_NUMBER,
    RE_SIEMENS_PN,
    ABBREV_MAP,
)

# ──────────────────────────────────────────────
# Результат нормализации
# ──────────────────────────────────────────────
@dataclass
class ElectronicsRecord:
    """Унифицированная запись для Splink-матчинга электронных компонентов."""

    source_id: str                           # ID из исходной системы
    source_type: str                         # "catalog" | "tender"
    text_raw: str                            # оригинальный текст

    # === Уровень 1: Part Number (exact match) ===
    part_numbers: list[str] = field(default_factory=list)  # нормализованные PN
    part_number_primary: str = ""            # основной PN (первый найденный)

    # === Уровень 2: Manufacturer ===
    manufacturer: str = ""                   # каноническое имя производителя

    # === Уровень 3: Category + Parameters ===
    category: str = ""                       # igbt, thyristor, fpga_cpld, ...
    params: dict = field(default_factory=dict)  # voltage_v, current_a, ...

    # === Мета ===
    name_clean: str = ""                     # очищенное описание (для fuzzy fallback)
    quantity: float | None = None
    unit: str = ""
    region: str = ""
    price_max: float | None = None
    match_scenario: str = ""                 # "A", "B", "C"
    extra: dict = field(default_factory=dict)


# ──────────────────────────────────────────────
# Regex: мусор
# ──────────────────────────────────────────────
_RE_JUNK = re.compile(r'[«»""„‟\[\]{}]')
_RE_SPACES = re.compile(r'\s+')
_RE_QTY = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(шт\.?|штук|компл\.?|уп\.?|партия|лот)',
    re.IGNORECASE
)


# ──────────────────────────────────────────────
# Основные шаги
# ──────────────────────────────────────────────

def _clean(text: str) -> str:
    text = _RE_JUNK.sub(' ', text.strip())
    return _RE_SPACES.sub(' ', text)


def _extract_part_numbers(text: str) -> list[str]:
    """
    Извлекает все part numbers из текста.
    Сначала проверяет специфичные паттерны (Siemens), потом общие.
    Фильтрует шум: слишком короткие, чисто числовые, известные слова.
    """
    # Стоп-слова: производители, общие термины — не part numbers
    _STOPWORDS = {
        "SIEMENS", "SIMATIC", "MITSUBISHI", "ELECTRIC", "XILINX", "ALTERA",
        "OMRON", "SEMIKRON", "INFINEON", "VISHAY", "MICROCHIP", "MICROSEMI",
        "FUJI", "POWERFLEX", "ALLEN-BRADLEY", "ROCKWELL", "HITACHI",
        "KINGBRIGHT", "QORVO", "CYPRESS", "MAXIM", "ATMEL", "KEMET",
        "IGBT", "MOSFET", "FPGA", "CPLD", "PLIS",
    }

    pns: list[str] = []

    # Шаг 0: склеиваем Siemens-style PN с пробелом ("6ES7 321-..." → "6ES7321-...")
    # Also handles "6EP 3436-..." and similar patterns
    text_fixed = re.sub(
        r'\b(\d[A-Z]{2}\d)\s+(\d{3,4}[\-])',
        r'\1\2', text, flags=re.IGNORECASE
    )

    # Siemens-style (более точный паттерн)
    for m in RE_SIEMENS_PN.finditer(text_fixed):
        pn = normalize_part_number(m.group(1))
        if pn not in pns:
            pns.append(pn)

    # Общие part numbers
    for m in RE_PART_NUMBER.finditer(text_fixed):
        raw = m.group(1)
        # Фильтрация шума
        if len(raw) < 5:
            continue
        if raw.isdigit():
            continue
        # Пропускаем чисто буквенные короткие слова
        if raw.isalpha() and len(raw) < 8:
            continue
        pn = normalize_part_number(raw)
        # Пропускаем стоп-слова
        if pn in _STOPWORDS:
            continue
        if pn not in pns:
            pns.append(pn)

    return pns


def _extract_quantity(text: str) -> tuple[float | None, str]:
    m = _RE_QTY.search(text)
    if m:
        qty = float(m.group(1).replace(',', '.'))
        unit = m.group(2).strip('.').lower()
        if unit in ('штук',):
            unit = 'шт'
        return qty, unit
    return None, ""


def _determine_scenario(rec: ElectronicsRecord) -> str:
    """
    Определяет сценарий матчинга:
      A — есть part number (exact match)
      B — есть категория + параметры (параметрический)
      C — только общее описание (широкий матч)
    """
    if rec.part_number_primary:
        return "A"
    elif rec.category and rec.params:
        return "B"
    else:
        return "C"


# ══════════════════════════════════════════════
# ПУБЛИЧНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════

def normalize_catalog_item(
    source_id: str,
    name: str,
    part_number: str = "",
    manufacturer: str = "",
    category: str = "",
    **extra,
) -> ElectronicsRecord:
    """
    Нормализация позиции из каталога Radal.

    В каталоге part number обычно есть как отдельное поле — передаём его напрямую.
    Если нет — извлекаем из name.
    """
    clean = _clean(name)

    # Part number
    if part_number:
        pns = [normalize_part_number(part_number)]
    else:
        pns = _extract_part_numbers(clean)

    # Из описания тоже могут быть доп. part numbers
    pns_from_text = _extract_part_numbers(clean)
    for pn in pns_from_text:
        if pn not in pns:
            pns.append(pn)

    # Manufacturer
    mfr = find_manufacturer(manufacturer) if manufacturer else find_manufacturer(clean)

    # Category
    cat = category or detect_category(clean)

    # Params
    params = extract_electrical_params(clean)

    rec = ElectronicsRecord(
        source_id=source_id,
        source_type="catalog",
        text_raw=name,
        part_numbers=pns,
        part_number_primary=pns[0] if pns else "",
        manufacturer=mfr,
        category=cat,
        params=params,
        name_clean=clean.lower(),
        extra=extra,
    )
    rec.match_scenario = _determine_scenario(rec)
    return rec


def normalize_tender_item(
    source_id: str,
    name: str,
    category: str = "",
    region: str = "",
    price_max: float | None = None,
    quantity_str: str = "",
    **extra,
) -> ElectronicsRecord:
    """
    Нормализация тендерной позиции.

    Тендер может содержать:
      - Точный part number (сценарий A — лучший случай)
      - Описание с параметрами (сценарий B)
      - Общее описание (сценарий C)
    """
    clean = _clean(name)

    # Part numbers
    pns = _extract_part_numbers(clean)

    # Manufacturer
    mfr = find_manufacturer(clean)

    # Category
    cat = category or detect_category(clean)

    # Params
    params = extract_electrical_params(clean)

    # Quantity
    qty, unit = _extract_quantity(quantity_str or clean)

    rec = ElectronicsRecord(
        source_id=source_id,
        source_type="tender",
        text_raw=name,
        part_numbers=pns,
        part_number_primary=pns[0] if pns else "",
        manufacturer=mfr,
        category=cat,
        params=params,
        name_clean=clean.lower(),
        quantity=qty,
        unit=unit,
        region=region,
        price_max=price_max,
        extra=extra,
    )
    rec.match_scenario = _determine_scenario(rec)
    return rec
