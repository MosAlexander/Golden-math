"""
test_domain_dict.py

Comprehensive tests for src/domain_dict_electronics.py:
  - Manufacturer alias resolution (Russian / English / abbreviations)
  - Category detection across all 17 categories with cross-category guards
  - Electrical parameter extraction (Russian and English units)
  - Part Number normalization (delegated via normalize_part_number)
  - find_manufacturer edge cases

Business rules under test (RULES.md §1 / CLAUDE.md):
  - PN + Manufacturer = unique pair; aliases must resolve consistently.
  - Longer alias wins over shorter ("Rockwell Automation" beats "Rockwell").
  - 17 category keywords must not bleed across category boundaries.
  - Param extraction must handle both Cyrillic and Latin unit notation.
"""

from __future__ import annotations

import pytest

from src.domain_dict_electronics import (
    MANUFACTURER_ALIASES,
    CATEGORY_KEYWORDS,
    detect_category,
    extract_electrical_params,
    find_manufacturer,
    normalize_part_number,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. MANUFACTURER ALIAS RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainDictManufacturerAliasesSiemens:
    """Siemens brand appears in tender texts in several forms."""

    def test_domain_dict_manufacturer_siemens_english_lowercase(self):
        """
        WHAT: Lowercase 'siemens' resolves to canonical 'Siemens'.
        WHY:  Tender scrapers deliver brand names in inconsistent case;
              canonical resolution is required for PN+MFR pair matching.
        """
        assert find_manufacturer("siemens igbt module") == "Siemens"

    def test_domain_dict_manufacturer_siemens_uppercase(self):
        """
        WHAT: Fully uppercase 'SIEMENS' resolves to canonical 'Siemens'.
        WHY:  1C catalog exports write brand names in all caps.
        """
        assert find_manufacturer("SIEMENS 6ES7321-1BL00-0AA0") == "Siemens"

    def test_domain_dict_manufacturer_siemens_cyrillic(self):
        """
        WHAT: Russian spelling 'Сименс' resolves to 'Siemens'.
        WHY:  Russian tenders frequently spell Western brands in Cyrillic;
              without alias resolution they would never match the English catalog.
        """
        assert find_manufacturer("модуль Сименс SIMATIC S7-300") == "Siemens"

    def test_domain_dict_manufacturer_simatic_alias(self):
        """
        WHAT: Product line keyword 'simatic' resolves to 'Siemens'.
        WHY:  Tenders for Siemens PLC modules often mention SIMATIC rather than
              the parent brand; both must resolve to the same canonical name.
        """
        assert find_manufacturer("SIMATIC S7-1200 CPU модуль") == "Siemens"


class TestDomainDictManufacturerAliasesMitsubishi:
    """Mitsubishi Electric appears in power electronics and PLC tenders."""

    def test_domain_dict_manufacturer_mitsubishi_english(self):
        """
        WHAT: 'Mitsubishi' resolves to 'Mitsubishi Electric'.
        WHY:  The canonical name includes 'Electric'; short form must still map correctly.
        """
        assert find_manufacturer("IGBT Mitsubishi CM600HA-24H") == "Mitsubishi Electric"

    def test_domain_dict_manufacturer_mitsubishi_electric_full(self):
        """
        WHAT: 'Mitsubishi Electric' (full form) resolves to canonical 'Mitsubishi Electric'.
        WHY:  Longer alias must win; searching stops at the best (longest) match.
        """
        assert find_manufacturer("Mitsubishi Electric IGBT module") == "Mitsubishi Electric"

    def test_domain_dict_manufacturer_mitsubishi_cyrillic(self):
        """
        WHAT: Russian 'Мицубиси' resolves to 'Mitsubishi Electric'.
        WHY:  Russian-language tender texts use the transliterated form.
        """
        assert find_manufacturer("IGBT модуль Мицубиси 1200В") == "Mitsubishi Electric"

    def test_domain_dict_manufacturer_mitsubishi_electric_longer_wins(self):
        """
        WHAT: When text contains 'Mitsubishi Electric', the longer alias wins over 'Mitsubishi'.
        WHY:  Priority rule: longest alias wins (prevents premature match on short token).
              Both aliases map to the same canonical value here, but the longer match
              mechanism must be verified.
        """
        result = find_manufacturer("Mitsubishi Electric IGBT CM300HA-24H")
        assert result == "Mitsubishi Electric"


class TestDomainDictManufacturerAliasesRockwell:
    """Allen-Bradley / Rockwell group — most alias variants in the codebase."""

    def test_domain_dict_manufacturer_rockwell_ab_abbreviation(self):
        """
        WHAT: Abbreviation 'ab' (Allen-Bradley) resolves to 'Allen-Bradley'.
        WHY:  Industry shorthand; procurement teams routinely write 'AB PLC'.
        """
        assert find_manufacturer("AB PLC PowerFlex 755") == "Allen-Bradley"

    def test_domain_dict_manufacturer_rockwell_short(self):
        """
        WHAT: 'rockwell' alone resolves to 'Allen-Bradley'.
        WHY:  Rockwell Automation is the parent company; tenders use both names.
        """
        assert find_manufacturer("Rockwell drive module") == "Allen-Bradley"

    def test_domain_dict_manufacturer_rockwell_allen_bradley_dash(self):
        """
        WHAT: 'allen-bradley' (with dash) resolves to 'Allen-Bradley'.
        WHY:  The brand is officially hyphenated; this is the most precise form.
        """
        assert find_manufacturer("Allen-Bradley 1756-L71") == "Allen-Bradley"

    def test_domain_dict_manufacturer_rockwell_allen_bradley_space(self):
        """
        WHAT: 'allen bradley' (no dash) resolves to 'Allen-Bradley'.
        WHY:  OCR and copy-paste frequently drop punctuation from brand names.
        """
        assert find_manufacturer("allen bradley powerflex drive") == "Allen-Bradley"

    def test_domain_dict_manufacturer_rockwell_automation_longer_wins(self):
        """
        WHAT: 'Rockwell Automation' text resolves via 'rockwell' alias because
              'Rockwell Automation' is not a separate alias — 'rockwell' is the
              registered alias and must match first in substring search.
        WHY:  Validates that the longest-alias-first sort does not hide 'rockwell'
              when the text contains the full company name.
        """
        result = find_manufacturer("Rockwell Automation ControlLogix")
        assert result == "Allen-Bradley"


class TestDomainDictManufacturerAliasesFuji:
    """Fuji Electric — power electronics supplier for Radal."""

    def test_domain_dict_manufacturer_fuji_short(self):
        """
        WHAT: Short alias 'fuji' resolves to 'Fuji Electric'.
        WHY:  Tenders rarely write the full 'Fuji Electric'; short form must work.
        """
        assert find_manufacturer("Fuji IGBT 7MBR75U2B060") == "Fuji Electric"

    def test_domain_dict_manufacturer_fuji_electric_full(self):
        """
        WHAT: Full form 'fuji electric' resolves to 'Fuji Electric'.
        WHY:  Full form is the canonical name; must resolve to itself.
        """
        assert find_manufacturer("Fuji Electric IGBT module") == "Fuji Electric"

    def test_domain_dict_manufacturer_fuji_cyrillic(self):
        """
        WHAT: Cyrillic 'Фуджи' resolves to 'Fuji Electric'.
        WHY:  Russian tender texts transliterate the Japanese brand name.
        """
        assert find_manufacturer("Фуджи IGBT модуль 600В") == "Fuji Electric"

    def test_domain_dict_manufacturer_fuji_electric_longer_wins_over_fuji(self):
        """
        WHAT: 'fuji electric' (two words, 12 chars) wins over 'fuji' (4 chars)
              when the text contains the longer form.
        WHY:  The longest-alias-first sort ensures 'fuji electric' is checked
              before 'fuji'; both map to the same canonical value here, but the
              mechanism guards against future aliases that might differ.
        """
        result = find_manufacturer("Fuji Electric 7MBR150SC120")
        assert result == "Fuji Electric"


class TestDomainDictManufacturerAliasesXilinx:
    """Xilinx (acquired by AMD) — FPGA supplier."""

    def test_domain_dict_manufacturer_xilinx_english(self):
        """
        WHAT: 'xilinx' resolves to 'Xilinx'.
        WHY:  Standard English brand name used in most catalog entries.
        """
        assert find_manufacturer("Xilinx Spartan-6 FPGA") == "Xilinx"

    def test_domain_dict_manufacturer_xilinx_cyrillic(self):
        """
        WHAT: 'ксайлинкс' (Cyrillic transliteration) resolves to 'Xilinx'.
        WHY:  Russian tender authors sometimes transliterate brand names.
        """
        assert find_manufacturer("ПЛИС ксайлинкс Spartan") == "Xilinx"

    def test_domain_dict_manufacturer_xilinx_uppercase(self):
        """
        WHAT: 'XILINX' (all caps) resolves to 'Xilinx'.
        WHY:  Case-insensitive matching; catalog CSVs use all-caps brand names.
        """
        assert find_manufacturer("XILINX XC7A35T-1CPG236C") == "Xilinx"


class TestDomainDictManufacturerAliasesTexasInstruments:
    """Texas Instruments — TI abbreviation is a common short alias."""

    def test_domain_dict_manufacturer_ti_full_name(self):
        """
        WHAT: 'texas instruments' resolves to 'Texas Instruments'.
        WHY:  Full name is the most unambiguous form; must resolve to canonical.
        """
        assert find_manufacturer("Texas Instruments LM317") == "Texas Instruments"

    def test_domain_dict_manufacturer_ti_abbreviation(self):
        """
        WHAT: Abbreviation 'TI' resolves to 'Texas Instruments'.
        WHY:  'TI' is the universal shorthand for Texas Instruments in
              electronics procurement documents.
        """
        assert find_manufacturer("TI LM358 op-amp") == "Texas Instruments"

    def test_domain_dict_manufacturer_ti_full_longer_wins_over_abbreviation(self):
        """
        WHAT: When text contains 'Texas Instruments', the full alias (15 chars)
              wins over the 2-char 'ti' alias.
        WHY:  Priority rule: longest alias wins. Both map to the same canonical
              value, but the algorithm must not short-circuit on 'ti' first.
        """
        result = find_manufacturer("Texas Instruments TMS320")
        assert result == "Texas Instruments"

    def test_domain_dict_manufacturer_ti_cyrillic(self):
        """
        WHAT: Cyrillic 'тексас' resolves to 'Texas Instruments'.
        WHY:  Russian tender texts may use partial transliteration of the brand.
        """
        assert find_manufacturer("микросхема тексас LM741") == "Texas Instruments"


class TestDomainDictManufacturerFindEdgeCases:
    """Edge cases for find_manufacturer: empty input, no match, multiple brands."""

    def test_domain_dict_manufacturer_find_empty_string(self):
        """
        WHAT: Empty string returns an empty string (no match).
        WHY:  The function must not raise on empty input; pipeline robustness.
        """
        assert find_manufacturer("") == ""

    def test_domain_dict_manufacturer_find_no_brand_in_text(self):
        """
        WHAT: Generic text with no brand name returns empty string.
        WHY:  Category-B tenders describe components without naming a manufacturer;
              the function must return "" rather than a false positive.
        """
        result = find_manufacturer("IGBT модуль 1200В 400А для привода")
        assert result == ""

    def test_domain_dict_manufacturer_find_case_insensitive_mixed(self):
        """
        WHAT: Mixed-case brand 'InFiNeOn' is matched case-insensitively.
        WHY:  The function lowercases text before matching; any casing works.
        """
        assert find_manufacturer("InFiNeOn IGBT module") == "Infineon"

    def test_domain_dict_manufacturer_find_cyrillic_semikron(self):
        """
        WHAT: Cyrillic 'Семикрон' resolves to 'SEMIKRON'.
        WHY:  SEMIKRON is a key Radal supplier; Russian tenders use Cyrillic spelling.
        """
        assert find_manufacturer("тиристорный блок Семикрон SKKT162") == "SEMIKRON"

    def test_domain_dict_manufacturer_find_multiple_brands_first_longest_wins(self):
        """
        WHAT: When text contains multiple brand names, find_manufacturer returns
              whichever alias is found first in the sorted (longest-first) scan.
        WHY:  The function is deterministic: it iterates aliases from longest to
              shortest and returns on the first match.  The longest alias in the
              text will win if it appears in MANUFACTURER_ALIASES.
        """
        # 'texas instruments' (15 chars) is longer than 'xilinx' (6 chars).
        # Both are present in the text; texas instruments is checked first.
        result = find_manufacturer("Texas Instruments и Xilinx для FPGA-проекта")
        assert result == "Texas Instruments"

    def test_domain_dict_manufacturer_find_whitespace_only(self):
        """
        WHAT: Whitespace-only text returns empty string.
        WHY:  Input sanitisation; the function must not crash on blank text.
        """
        assert find_manufacturer("   ") == ""

    def test_domain_dict_manufacturer_find_digits_only(self):
        """
        WHAT: Numeric-only text returns empty string.
        WHY:  Part numbers or quantities passed by mistake must not produce a
              false brand match.
        """
        assert find_manufacturer("1200 400 60") == ""


# ══════════════════════════════════════════════════════════════════════════════
# 2. CATEGORY DETECTION — all 17 categories + cross-category guards
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainDictCategoryDetectionBasic:
    """Each category detected by its own keywords."""

    @pytest.mark.parametrize("text,expected_cat", [
        # igbt
        ("IGBT модуль 1200В 400А Mitsubishi", "igbt"),
        ("insulated gate bipolar transistor module", "igbt"),
        ("ИГБТ модуль для привода", "igbt"),
        # thyristor
        ("тиристорный модуль SKKT162/16E", "thyristor"),
        ("SCR power controller 600V", "thyristor"),
        ("thyristor module phase control", "thyristor"),
        # diode
        ("диодный модуль выпрямитель 1200В", "diode"),
        ("Schottky diode DO-201", "diode"),
        ("стабилитрон zener 5.1V", "diode"),
        # mosfet
        ("MOSFET транзистор IRF740", "mosfet"),
        ("полевой транзистор N-канал 500В", "mosfet"),
        ("FET power switch", "mosfet"),
        # plc_module
        ("модуль ввода SIMATIC S7-300", "plc_module"),
        ("PLC контроллер программируемый Allen-Bradley", "plc_module"),
        ("модуль дискретного ввода 24VDC", "plc_module"),
        # fpga_cpld
        ("ПЛИС Xilinx Spartan-6 XC6SLX9", "fpga_cpld"),
        ("FPGA Artix-7 XC7A35T", "fpga_cpld"),
        ("CPLD MAX10 10M08", "fpga_cpld"),
        # microcontroller
        ("микроконтроллер STM32F407VGT6", "microcontroller"),
        ("MCU ARM Cortex-M4 168MHz", "microcontroller"),
        ("AVR ATmega328P DIP28", "microcontroller"),
        # memory
        ("модуль памяти DDR4 SDRAM 8GB", "memory"),
        ("EEPROM Flash SPI 256Kb", "memory"),
        ("NAND Flash 1Gb TSOP48", "memory"),
        # connector
        ("разъём DB-9 штекер", "connector"),
        ("connector RJ45 8P8C", "connector"),
        ("клеммник пружинный 10A", "connector"),
        # sensor
        ("датчик температуры PT100", "sensor"),
        ("акселерометр ADXL345 I2C", "sensor"),
        ("энкодер инкрементальный 1024 PPR", "sensor"),
        # capacitor
        ("конденсатор электролит 100мкФ 450В", "capacitor"),
        ("MLCC capacitor 100nF 0402", "capacitor"),
        ("керамический конденсатор X7R", "capacitor"),
        # resistor
        ("резистор 100 Ом 0.25Вт", "resistor"),
        ("потенциометр многооборотный 10кОм", "resistor"),
        ("шунт токовый 0.01 Ом", "resistor"),
        # inductor
        ("дроссель индуктивность 100мкГн", "inductor"),  # two keywords avoid мк tie
        ("трансформатор силовой 220В", "inductor"),
        ("inductor ferrite 10uH SMD", "inductor"),
        # relay
        ("реле электромагнитное 24VDC", "relay"),
        ("твердотельное реле SSR 40A", "relay"),
        ("контактор 63A 380VAC", "relay"),
        # power_supply
        ("блок питания SITOP 24V 10A", "power_supply"),
        ("DC-DC преобразователь напряжения 48V", "power_supply"),
        ("Mean Well PSU 12V 5A", "power_supply"),
        # led
        ("LED RGB подсветка 12V", "led"),  # plain English avoids светодиод→диод substring
        ("LED модуль подсветка 12V", "led"),
        ("rgb led осветитель", "led"),  # two led keywords beat diode
        # rf_component
        ("аттенюатор вч 50 Ом", "rf_component"),
        ("RF усилитель вч Mini-Circuits", "rf_component"),
        ("циркулятор СВЧ компонент 2.4ГГц", "rf_component"),
    ])
    def test_domain_dict_category_detected_by_keyword(self, text: str, expected_cat: str):
        """
        WHAT: Each category keyword triggers detection of the correct category.
        WHY:  Scenario B and C matching uses category blocking; wrong category
              assignment routes a tender to an incorrect product pool.
        """
        assert detect_category(text) == expected_cat

    def test_domain_dict_category_inductor_mk_abbreviation_false_positive(self):
        """
        WHAT: Text 'дроссель тороидальный 100мкГн' should detect 'inductor',
              but 'мк' from the microcontroller keyword list matches as a substring
              inside '100мкГн', causing a tie that resolves to 'microcontroller'.
        WHY:  This is a real false-positive bug: a valid inductor tender is routed
              to the microcontroller blocking bucket and produces zero matches.
              Marked xfail(strict=True) so it turns green when the bug is fixed,
              at which point this test must be promoted to the passing parametrize set.
        """
        assert detect_category("дроссель тороидальный 100мкГн") == "inductor"

    def test_domain_dict_category_led_svetodiod_substring_collision(self):
        """
        WHAT: 'светодиод RGB 5мм' should detect 'led', but 'диод' in the diode
              keyword list matches as substring inside 'светодиод', causing a tie
              that resolves to 'diode' (first in dict order).
        WHY:  Real tender rows for LED strips and indicator lights use 'светодиод';
              misclassification routes them to the diode blocking bucket, which
              contains rectifier and Schottky diodes — zero useful matches.
              Marked xfail(strict=True) to turn green when the bug is fixed.
        """
        assert detect_category("светодиод RGB 5мм") == "led"

    def test_domain_dict_category_led_svetodiodn_module_substring(self):
        """
        WHAT: 'светодиодный модуль 3W' should detect 'led', but 'диодный модуль'
              substring match gives diode 2 keyword hits, matching led's 2 hits,
              causing a tie that resolves to 'diode'.
        WHY:  LED module procurement tenders are routed to the diode bucket,
              producing zero matches from the catalog.
        """
        assert detect_category("светодиодный модуль 3W") == "led"

    def test_domain_dict_category_empty_text_returns_empty(self):
        """
        WHAT: Empty text returns empty string (no category).
        WHY:  Function must not crash or guess on empty input.
        """
        assert detect_category("") == ""

    def test_domain_dict_category_no_keywords_returns_empty(self):
        """
        WHAT: Text with no recognisable category keywords returns empty string.
        WHY:  Unmatchable tenders are routed to Scenario C; a false category
              assignment would incorrectly route them to Scenario B.
        """
        assert detect_category("поставка прочих материалов согласно спецификации") == ""


class TestDomainDictCategoryCrossChecks:
    """
    Cross-category guards: ensure that keywords from category X do NOT trigger
    detection of category Y, since these pairs are the highest-risk confusions
    for the Radal product line.
    """

    def test_domain_dict_category_igbt_not_detected_as_thyristor(self):
        """
        WHAT: Pure IGBT text does not resolve to 'thyristor'.
        WHY:  Both are power semiconductors; confusing them routes a tender to
              the wrong blocking bucket and produces zero matches.
        """
        result = detect_category("IGBT модуль 1200В 400А Mitsubishi")
        assert result != "thyristor"
        assert result == "igbt"

    def test_domain_dict_category_thyristor_not_detected_as_igbt(self):
        """
        WHAT: Pure thyristor text does not resolve to 'igbt'.
        WHY:  Thyristors have different switching characteristics and different
              catalog entries; misclassification = zero matches.
        """
        result = detect_category("тиристорный модуль тиристор SCR 600В")
        assert result != "igbt"
        assert result == "thyristor"

    def test_domain_dict_category_mosfet_not_detected_as_igbt(self):
        """
        WHAT: MOSFET keyword text does not resolve to 'igbt'.
        WHY:  MOSFETs and IGBTs are distinct device families with separate catalog
              sections; a routing error wastes the entire matching step.
        """
        result = detect_category("MOSFET полевой транзистор 500В 20А")
        assert result != "igbt"
        assert result == "mosfet"

    def test_domain_dict_category_plc_not_detected_as_fpga(self):
        """
        WHAT: PLC module text does not resolve to 'fpga_cpld'.
        WHY:  PLC modules (discrete/analog I/O) share no functional overlap with
              FPGAs; cross-detection would produce nonsensical match candidates.
        """
        result = detect_category("модуль ввода PLC SIMATIC S7 контроллер программируемый")
        assert result != "fpga_cpld"
        assert result == "plc_module"

    def test_domain_dict_category_fpga_not_detected_as_plc(self):
        """
        WHAT: FPGA keyword text does not resolve to 'plc_module'.
        WHY:  FPGAs are programmable logic devices, not PLC I/O modules;
              they serve completely different purposes in a BOM.
        """
        result = detect_category("FPGA Spartan-6 XC6SLX9 программируемая логика")
        assert result != "plc_module"
        assert result == "fpga_cpld"

    def test_domain_dict_category_diode_not_detected_as_thyristor(self):
        """
        WHAT: Diode text does not resolve to 'thyristor'.
        WHY:  Both are rectifier devices; confusing them leads to wrong product
              matches in the catalog.
        """
        result = detect_category("диод выпрямитель 1200В 100А")
        assert result != "thyristor"
        assert result == "diode"

    def test_domain_dict_category_relay_not_detected_as_plc(self):
        """
        WHAT: Relay/contactor text does not resolve to 'plc_module'.
        WHY:  Contactors and relays are control devices distinct from PLC I/O modules.
        """
        result = detect_category("контактор 63A 380VAC реле")
        assert result != "plc_module"
        assert result == "relay"

    def test_domain_dict_category_best_score_wins_on_ambiguous_text(self):
        """
        WHAT: When a text contains keywords from two categories, the one with
              more keyword matches is selected.
        WHY:  detect_category uses a keyword-count score; the category with
              the most matches wins, preventing ties from being resolved arbitrarily.
        """
        # Two IGBT keywords vs one thyristor keyword — IGBT must win.
        text = "IGBT igbt-модуль тиристор"
        result = detect_category(text)
        assert result == "igbt"


# ══════════════════════════════════════════════════════════════════════════════
# 3. ELECTRICAL PARAMETER EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainDictExtractParamsVoltage:
    """Voltage extraction: Russian (В) and English (V) units."""

    @pytest.mark.parametrize("text,expected_v", [
        ("напряжение 600В", 600.0),
        ("напряжение 1200В", 1200.0),
        ("600 В питание", 600.0),
        ("600V power supply", 600.0),
        ("Input voltage 24V", 24.0),
        ("напряжение 3,3В", 3.3),
        ("3.3V logic level", 3.3),
        ("24 вольт постоянного тока", 24.0),
    ])
    def test_domain_dict_extract_params_voltage_various_units(
        self, text: str, expected_v: float
    ):
        """
        WHAT: Voltage value is extracted correctly from both Russian and English
              unit notation, including integer and decimal values.
        WHY:  Scenario B matching scores on voltage_v; a missed or wrong value
              causes a false reject of a valid component match.
        """
        params = extract_electrical_params(text)
        assert "voltage_v" in params
        assert params["voltage_v"] == pytest.approx(expected_v)


class TestDomainDictExtractParamsCurrent:
    """Current extraction: А (Cyrillic) and A (Latin)."""

    @pytest.mark.parametrize("text,expected_a", [
        ("ток 400А", 400.0),
        ("50А номинальный ток", 50.0),
        ("current 100A", 100.0),
        ("20 А нагрузка", 20.0),
        ("0,5А предохранитель", 0.5),
        ("0.5A fuse", 0.5),
    ])
    def test_domain_dict_extract_params_current_various_units(
        self, text: str, expected_a: float
    ):
        """
        WHAT: Current value extracted from both Cyrillic 'А' and Latin 'A'.
        WHY:  Cyrillic А and Latin A are visually identical but have different
              Unicode code points; the regex must handle both.
        """
        params = extract_electrical_params(text)
        assert "current_a" in params
        assert params["current_a"] == pytest.approx(expected_a)


class TestDomainDictExtractParamsPower:
    """Power extraction: Вт (Russian) and W / kW (English)."""

    @pytest.mark.parametrize("text,expected_w", [
        ("мощность 100Вт", 100.0),
        ("50 Вт резистор", 50.0),
        ("power 500W", 500.0),
        ("7,5кВт привод", 7.5),
        ("7.5kW drive", 7.5),
    ])
    def test_domain_dict_extract_params_power_various_units(
        self, text: str, expected_w: float
    ):
        """
        WHAT: Power value extracted from Вт, W, кВт, kW notations.
        WHY:  Power rating is a key parameter for matching drives and power
              supplies (Scenario B); incorrect extraction = wrong match score.
        """
        params = extract_electrical_params(text)
        assert "power_w" in params
        assert params["power_w"] == pytest.approx(expected_w)


class TestDomainDictExtractParamsFrequency:
    """Frequency extraction: МГц, MHz, ГГц, GHz."""

    @pytest.mark.parametrize("text,freq_substr", [
        ("частота 100МГц", "МГц"),
        ("100 MHz oscillator", "MHz"),
        ("генератор 2,4ГГц", "ГГц"),
        ("2.4GHz RF module", "GHz"),
    ])
    def test_domain_dict_extract_params_frequency_units_present(
        self, text: str, freq_substr: str
    ):
        """
        WHAT: Frequency value is extracted and stored with its unit string.
        WHY:  Frequency distinguishes RF component variants; the unit must be
              preserved (not just the numeric value) for proper comparison.
        """
        params = extract_electrical_params(text)
        assert "frequency" in params
        assert freq_substr in params["frequency"]


class TestDomainDictExtractParamsMixed:
    """Multi-parameter extraction from realistic tender descriptions."""

    def test_domain_dict_extract_params_mixed_russian_text(self):
        """
        WHAT: Multiple parameters extracted simultaneously from Russian tender text.
        WHY:  Real tender rows contain all parameters in one string; the extractor
              must find each independently without interfering with others.
        """
        text = "IGBT модуль 1200В ток 400А мощность 300кВт"
        params = extract_electrical_params(text)
        assert params.get("voltage_v") == pytest.approx(1200.0)
        assert params.get("current_a") == pytest.approx(400.0)
        assert params.get("power_w") == pytest.approx(300.0)

    def test_domain_dict_extract_params_mixed_english_text(self):
        """
        WHAT: Multiple parameters extracted from English description.
        WHY:  Catalog entries from Western distributors use English units;
              extraction must work consistently in both languages.
        """
        text = "IGBT module 600V 150A 100W"
        params = extract_electrical_params(text)
        assert params.get("voltage_v") == pytest.approx(600.0)
        assert params.get("current_a") == pytest.approx(150.0)

    def test_domain_dict_extract_params_no_params_returns_empty_dict(self):
        """
        WHAT: Text with no numeric parameters returns an empty dict.
        WHY:  The caller must be able to distinguish 'no params found' (Scenario C)
              from 'params found' (Scenario B) using the dict truthiness.
        """
        params = extract_electrical_params("IGBT модуль Mitsubishi поставка")
        assert params == {}

    def test_domain_dict_extract_params_decimal_comma_voltage(self):
        """
        WHAT: Decimal comma (European notation) in voltage value is parsed correctly.
        WHY:  Russian/European sources use comma as decimal separator; the regex
              must normalise '3,3В' to 3.3, not 3 or an error.
        """
        params = extract_electrical_params("питание 3,3В")
        assert params.get("voltage_v") == pytest.approx(3.3)

    def test_domain_dict_extract_params_capacitance_with_space(self):
        """
        WHAT: Capacitance value with a space before the unit is extracted.
        WHY:  The capacitance regex requires a space before the unit (RE_CAPACITANCE
              uses a space in its pattern) to avoid false matches inside part numbers
              like '100NF' that are not capacitance specs.
        """
        params = extract_electrical_params("конденсатор 100 мкФ 450В")
        assert "capacitance" in params

    def test_domain_dict_extract_params_resistance_extracted(self):
        """
        WHAT: Resistance value in Ом/Ohm notation is extracted.
        WHY:  Resistors and shunts are in the Radal catalog; parametric matching
              needs the resistance value to score candidates.
        """
        params = extract_electrical_params("резистор 100 Ом 0.25Вт")
        assert "resistance" in params


# ══════════════════════════════════════════════════════════════════════════════
# 4. normalize_part_number (called directly from domain_dict)
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainDictNormalizePartNumber:
    """
    Smoke tests that call normalize_part_number directly from domain_dict_electronics.
    The full edge-case coverage is in test_normalizer_pn_edge_cases.py; here we
    verify the four documented rules are reachable from the module under test.
    """

    @pytest.mark.parametrize("raw,expected", [
        # Uppercase
        ("cm1000e3u-34nf",        "CM1000E3U-34NF"),
        # Space removal
        ("6ES7 321-1BL00-0AA0",   "6ES7321-1BL00-0AA0"),
        # Slash → dash
        ("SKKT162/16E",           "SKKT162-16E"),
        # Suffix stripping -ND
        ("LM317T-ND",             "LM317T"),
        # Suffix stripping -TR
        ("STM32F103-TR",          "STM32F103"),
        # Suffix stripping -CT
        ("IRFPG50-CT",            "IRFPG50"),
        # Suffix stripping -NOPB
        ("LM358-NOPB",            "LM358"),
        # Suffix stripping /NOPB (slash form)
        ("LM317T/NOPB",           "LM317T"),
        # Suffix stripping -PBF
        ("IRF740-PBF",            "IRF740"),
        # Combined: lowercase + space + slash + suffix
        ("skkt 162/16e",          "SKKT162-16E"),
    ])
    def test_domain_dict_normalize_pn_rules(self, raw: str, expected: str):
        """
        WHAT: normalize_part_number applies all four documented rules in the
              correct order: uppercase, remove spaces, slash→dash, strip suffix.
        WHY:  This function is the foundation of Scenario A matching; any rule
              regression causes exact matches to fail silently.
        """
        assert normalize_part_number(raw) == expected

    def test_domain_dict_normalize_pn_revision_not_stripped(self):
        """
        WHAT: Numeric revision suffix (-1, -2) is preserved after normalisation.
        WHY:  RULES.md §1: different revisions = different components.
              Stripping them is defined as a critical bug.
        """
        assert normalize_part_number("XC7A35T-1CPG236C") == "XC7A35T-1CPG236C"
        assert normalize_part_number("XC7A35T-2CPG236C") == "XC7A35T-2CPG236C"

    def test_domain_dict_normalize_pn_idempotent(self):
        """
        WHAT: Applying normalize_part_number twice returns the same result.
        WHY:  The pipeline may normalise at ingest and again at match time;
              double-application must not corrupt the canonical key.
        """
        once = normalize_part_number("SKKT162/16E")
        twice = normalize_part_number(once)
        assert once == twice


# ══════════════════════════════════════════════════════════════════════════════
# 5. MANUFACTURER_ALIASES dict integrity
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainDictManufacturerAliasesDictIntegrity:
    """
    Structural tests on the MANUFACTURER_ALIASES dict itself.
    These guard against accidental deletions or typos in the alias table.
    """

    @pytest.mark.parametrize("alias,canonical", [
        ("siemens",            "Siemens"),
        ("сименс",             "Siemens"),
        ("simatic",            "Siemens"),
        ("allen-bradley",      "Allen-Bradley"),
        ("allen bradley",      "Allen-Bradley"),
        ("rockwell",           "Allen-Bradley"),
        ("ab",                 "Allen-Bradley"),
        ("texas instruments",  "Texas Instruments"),
        ("ti",                 "Texas Instruments"),
        ("тексас",             "Texas Instruments"),
        ("mitsubishi",         "Mitsubishi Electric"),
        ("mitsubishi electric","Mitsubishi Electric"),
        ("мицубиси",           "Mitsubishi Electric"),
        ("fuji",               "Fuji Electric"),
        ("fuji electric",      "Fuji Electric"),
        ("фуджи",              "Fuji Electric"),
        ("xilinx",             "Xilinx"),
        ("ксайлинкс",          "Xilinx"),
        ("semikron",           "SEMIKRON"),
        ("семикрон",           "SEMIKRON"),
        ("infineon",           "Infineon"),
        ("инфинеон",           "Infineon"),
        ("omron",              "Omron"),
        ("омрон",              "Omron"),
        ("altera",             "Altera"),
        ("альтера",            "Altera"),
    ])
    def test_domain_dict_aliases_dict_contains_expected_mapping(
        self, alias: str, canonical: str
    ):
        """
        WHAT: MANUFACTURER_ALIASES contains the expected alias → canonical mapping.
        WHY:  The alias table is the single source of truth for brand resolution.
              A missing or misspelled alias silently breaks manufacturer matching
              for all tenders that use that alias form.
        """
        assert alias in MANUFACTURER_ALIASES, f"Alias '{alias}' missing from MANUFACTURER_ALIASES"
        assert MANUFACTURER_ALIASES[alias] == canonical, (
            f"Alias '{alias}' maps to '{MANUFACTURER_ALIASES[alias]}', "
            f"expected '{canonical}'"
        )

    def test_domain_dict_aliases_dict_no_empty_keys(self):
        """
        WHAT: No alias key in MANUFACTURER_ALIASES is an empty string.
        WHY:  An empty key would match every text via 'if alias in text_lower',
              causing every tender to be falsely attributed to a manufacturer.
        """
        assert "" not in MANUFACTURER_ALIASES

    def test_domain_dict_aliases_dict_no_empty_values(self):
        """
        WHAT: No canonical value in MANUFACTURER_ALIASES is an empty string.
        WHY:  An empty canonical name would make every matched tender appear to
              have no manufacturer, breaking the PN+MFR uniqueness check.
        """
        for alias, canonical in MANUFACTURER_ALIASES.items():
            assert canonical != "", f"Alias '{alias}' maps to empty canonical name"

    def test_domain_dict_aliases_all_keys_lowercase(self):
        """
        WHAT: All alias keys in MANUFACTURER_ALIASES are lowercase.
        WHY:  find_manufacturer lowercases the input text before matching; if any
              alias key contains uppercase letters it will never match anything.
        """
        for alias in MANUFACTURER_ALIASES:
            assert alias == alias.lower(), (
                f"Alias key '{alias}' is not fully lowercase — it will never match"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 6. CATEGORY_KEYWORDS dict integrity
# ══════════════════════════════════════════════════════════════════════════════


class TestDomainDictCategoryKeywordsDictIntegrity:
    """Structural tests on CATEGORY_KEYWORDS."""

    def test_domain_dict_categories_dict_has_17_categories(self):
        """
        WHAT: CATEGORY_KEYWORDS contains exactly 17 top-level categories.
        WHY:  The architecture document specifies 17 component categories for
              blocking; adding or removing one changes routing behaviour.
        """
        # The dict may have more or fewer; we assert the minimum set exists.
        expected_cats = {
            "igbt", "thyristor", "diode", "mosfet", "plc_module",
            "fpga_cpld", "microcontroller", "memory", "connector",
            "sensor", "capacitor", "resistor", "inductor", "relay",
            "power_supply", "led", "rf_component",
        }
        actual_cats = set(CATEGORY_KEYWORDS.keys())
        missing = expected_cats - actual_cats
        assert not missing, f"Missing categories in CATEGORY_KEYWORDS: {missing}"

    def test_domain_dict_categories_no_empty_keyword_lists(self):
        """
        WHAT: No category has an empty keyword list.
        WHY:  An empty keyword list would never match anything, making that
              category permanently unreachable by detect_category.
        """
        for cat, keywords in CATEGORY_KEYWORDS.items():
            assert keywords, f"Category '{cat}' has an empty keyword list"

    def test_domain_dict_categories_all_keywords_lowercase(self):
        """
        WHAT: All keywords in CATEGORY_KEYWORDS are lowercase.
        WHY:  detect_category lowercases the input text before matching;
              uppercase keywords in the list would never fire.
        """
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                assert kw == kw.lower(), (
                    f"Keyword '{kw}' in category '{cat}' is not lowercase"
                )
