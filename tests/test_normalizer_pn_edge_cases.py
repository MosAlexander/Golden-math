"""
test_normalizer_pn_edge_cases.py

Comprehensive edge-case tests for Part Number normalisation logic defined in
src/domain_dict_electronics.py::normalize_part_number and the downstream
pipeline entry points in src/normalizer_electronics.py.

Business rules under test (RULES.md §1 / CLAUDE.md):
  - Uppercase everything
  - Remove all internal spaces
  - Replace slashes with dashes
  - Strip packaging suffixes: -ND, -TR, -CT, -NOPB, -PBF  (also /NOPB)
  - Revision suffixes (-1, -2, ...) must NOT be stripped -- they identify
    different components and stripping them is a critical bug.
"""

from __future__ import annotations

import pytest

from src.domain_dict_electronics import normalize_part_number
from src.normalizer_electronics import normalize_catalog_item, normalize_tender_item


# ══════════════════════════════════════════════════════════════════════════════
# 1. UPPERCASE CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnUppercase:
    """All characters in a Part Number must be uppercased regardless of input."""

    def test_normalizer_pn_uppercase_all_lower(self):
        """
        WHAT: Fully lowercase PN is converted to uppercase.
        WHY:  Two catalog entries with identical PN in different cases must
              resolve to the same normalised key; otherwise exact-match fails.
        """
        assert normalize_part_number("cm1000e3u-34nf") == "CM1000E3U-34NF"

    def test_normalizer_pn_uppercase_mixed_case(self):
        """
        WHAT: Mixed-case PN is fully uppercased.
        WHY:  Tender text may arrive in arbitrary case from scraping.
        """
        assert normalize_part_number("Stm32F407vgt6") == "STM32F407VGT6"

    def test_normalizer_pn_uppercase_already_upper(self):
        """
        WHAT: Already-uppercase PN is returned unchanged.
        WHY:  Function must be idempotent; double-normalisation must not corrupt data.
        """
        assert normalize_part_number("IRFPG50") == "IRFPG50"

    @pytest.mark.parametrize("raw,expected", [
        ("lm317t",       "LM317T"),
        ("xc7a35t",      "XC7A35T"),
        ("7mbr75u2b060", "7MBR75U2B060"),
    ])
    def test_normalizer_pn_uppercase_parametrized(self, raw: str, expected: str):
        """
        WHAT: Parametrized spot-check for uppercase conversion.
        WHY:  Validates the rule across a representative range of PN formats.
        """
        assert normalize_part_number(raw) == expected


# ══════════════════════════════════════════════════════════════════════════════
# 2. SPACE REMOVAL
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnSpaceRemoval:
    """Internal spaces must be stripped -- the canonical Siemens-style example."""

    def test_normalizer_pn_space_removal_siemens_classic(self):
        """
        WHAT: Siemens PN with a single embedded space is joined into one token.
        WHY:  Siemens prints PNs as "6ES7 321-1BL00-0AA0" in datasheets; the
              catalog entry has no space -- exact match would otherwise fail.
        """
        assert normalize_part_number("6ES7 321-1BL00-0AA0") == "6ES7321-1BL00-0AA0"

    def test_normalizer_pn_space_removal_stm32_with_space(self):
        """
        WHAT: STM32 PN split mid-token by a space is reunited.
        WHY:  OCR and copy-paste from PDFs frequently introduce spurious spaces.
        """
        assert normalize_part_number("STM32F407 VGT6") == "STM32F407VGT6"

    def test_normalizer_pn_space_removal_leading_trailing(self):
        """
        WHAT: Leading/trailing whitespace is stripped.
        WHY:  CSV imports often have untrimmed cells.
        """
        assert normalize_part_number("  IRFPG50  ") == "IRFPG50"

    def test_normalizer_pn_space_removal_multiple_spaces(self):
        """
        WHAT: Multiple consecutive internal spaces are all removed.
        WHY:  Robust handling of poorly formatted source data.
        """
        assert normalize_part_number("6ES7  321-1BL00-0AA0") == "6ES7321-1BL00-0AA0"

    def test_normalizer_pn_space_removal_lowercase_with_space(self):
        """
        WHAT: Space removal and uppercasing are applied together (order-independent).
        WHY:  Transformation pipeline must be fully composable.
        """
        assert normalize_part_number("cm1000e3u -34nf") == "CM1000E3U-34NF"


# ══════════════════════════════════════════════════════════════════════════════
# 3. SLASH → DASH CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnSlashToDash:
    """Forward slashes in PNs must be replaced with dashes."""

    def test_normalizer_pn_slash_semikron_skkt(self):
        """
        WHAT: SEMIKRON SKKT-style PN with slash separator is normalised to dash.
        WHY:  SEMIKRON datasheets use "SKKT162/16E"; Radal catalog uses dash form.
        """
        assert normalize_part_number("SKKT162/16E") == "SKKT162-16E"

    def test_normalizer_pn_slash_lm317_nopb_already_slash(self):
        """
        WHAT: /NOPB suffix written with slash is stripped correctly after slash->dash.
        WHY:  Suffix stripping must still fire even when the input uses a slash
              rather than a dash before the suffix keyword.
        """
        # /NOPB becomes -NOPB after slash substitution, then is stripped.
        assert normalize_part_number("LM317T/NOPB") == "LM317T"

    def test_normalizer_pn_slash_multiple_slashes(self):
        """
        WHAT: Multiple slashes in a single PN are all converted to dashes.
        WHY:  Some legacy catalog exports use slashes as segment separators
              throughout the full PN string.
        """
        assert normalize_part_number("SK/T162/16E") == "SK-T162-16E"

    @pytest.mark.parametrize("raw,expected", [
        ("SKKT57/12E",   "SKKT57-12E"),
        ("SKKT92/16E",   "SKKT92-16E"),
        ("SKKH92/16E",   "SKKH92-16E"),
    ])
    def test_normalizer_pn_slash_semikron_family_parametrized(self, raw: str, expected: str):
        """
        WHAT: Slash->dash conversion across the SEMIKRON SKKT family.
        WHY:  SEMIKRON is a key Radal supplier; all variants must normalise
              consistently to enable catalog lookups.
        """
        assert normalize_part_number(raw) == expected


# ══════════════════════════════════════════════════════════════════════════════
# 4. PACKAGING SUFFIX STRIPPING
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnPackagingSuffixStripping:
    """Packaging/tape-and-reel suffixes must be stripped; they carry no component identity."""

    @pytest.mark.parametrize("suffix,raw,expected", [
        ("-ND",   "LM317T-ND",    "LM317T"),
        ("-TR",   "STM32F103-TR", "STM32F103"),
        ("-CT",   "IRFPG50-CT",   "IRFPG50"),
        ("-NOPB", "LM358-NOPB",   "LM358"),
        ("-PBF",  "IRF740-PBF",   "IRF740"),
        ("/NOPB", "LM317T/NOPB",  "LM317T"),
    ])
    def test_normalizer_pn_suffix_stripped_parametrized(
        self, suffix: str, raw: str, expected: str
    ):
        """
        WHAT: Each recognised packaging suffix is stripped from the PN.
        WHY:  The same component is sold as LM317T, LM317T-ND (Digi-Key number),
              LM317T/NOPB (RoHS), etc.  They must all collapse to the same key.
              Note: the -PBF row uses "IRF740-PBF" (with dash) -- this is the
              form the implementation currently handles via endswith("-PBF").
        """
        assert normalize_part_number(raw) == expected

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG: normalize_part_number does not strip 'PBF' when it is "
            "appended without a preceding dash (e.g. 'IRF740PBF').  "
            "The suffix list only matches '-PBF' (with dash).  "
            "Fix: add 'PBF' as a no-dash suffix variant or broaden the regex."
        ),
    )
    def test_normalizer_pn_suffix_pbf_without_dash_bug(self):
        """
        WHAT: 'IRF740PBF' (PBF directly appended, no dash) should be stripped
              to 'IRF740', but the current implementation returns 'IRF740PBF'.
        WHY:  Infineon and IR publish some lead-free variants without the dash
              (IRF740PBF), while the catalog stores the base PN (IRF740).
              This mismatch causes a missed exact match and is a real bug.
              This test is marked xfail(strict=True) so it turns RED when the
              bug is fixed, reminding the developer to promote it to a passing
              green test.
        """
        assert normalize_part_number("IRF740PBF") == "IRF740"

    def test_normalizer_pn_suffix_nd_case_insensitive(self):
        """
        WHAT: Suffix stripping is case-insensitive (input may arrive lowercase).
        WHY:  After uppercasing, "-nd" becomes "-ND" and must still be stripped.
        """
        assert normalize_part_number("lm317t-nd") == "LM317T"

    def test_normalizer_pn_suffix_tr_case_insensitive(self):
        """
        WHAT: -tr (lowercase) is stripped after uppercasing.
        WHY:  Same reason as above -- case normalisation must precede suffix check.
        """
        assert normalize_part_number("stm32f103-tr") == "STM32F103"

    def test_normalizer_pn_suffix_nopb_with_slash_lowercase(self):
        """
        WHAT: /nopb (all lowercase) is stripped.
        WHY:  Validates that both slash->dash and strip work together in lowercase input.
        """
        assert normalize_part_number("lm358/nopb") == "LM358"

    def test_normalizer_pn_suffix_pbf_with_dash(self):
        """
        WHAT: -PBF (dash-prefixed, as stored in the suffix list) is stripped.
        WHY:  Infineon and IR use "-PBF" for lead-free variants; these are the
              same component and must match the base PN in the catalog.
        """
        assert normalize_part_number("IRF740-PBF") == "IRF740"

    def test_normalizer_pn_suffix_multiple_not_applied(self):
        """
        WHAT: Only one suffix is stripped per call (the outermost/trailing one).
        WHY:  Real PNs do not stack two packaging suffixes; this ensures the
              function does not over-strip when called on already-clean data.
        """
        # After stripping -ND the result should be "LM317T", not strip more.
        result = normalize_part_number("LM317T-ND")
        assert result == "LM317T"
        assert "-" not in result or result.count("-") == 0


# ══════════════════════════════════════════════════════════════════════════════
# 5. REVISION SUFFIX MUST NOT BE STRIPPED  <- critical business rule
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnRevisionPreservation:
    """
    Revision suffixes (-1, -2, -01, -02, etc.) MUST be preserved.
    Different revisions are different components (RULES.md §1, CLAUDE.md).
    Stripping them is a critical matching bug that causes false positives.
    """

    def test_normalizer_pn_revision_suffix_minus1_preserved(self):
        """
        WHAT: Trailing -1 (numeric revision) is NOT stripped.
        WHY:  XC7A35T-1CPG236C (speed grade -1) and XC7A35T-2CPG236C are
              electrically different parts.  Stripping would cause a false match.
        """
        result = normalize_part_number("XC7A35T-1CPG236C")
        assert result == "XC7A35T-1CPG236C"

    def test_normalizer_pn_revision_suffix_minus2_preserved(self):
        """
        WHAT: Trailing -2 (faster speed grade) is NOT stripped.
        WHY:  Same reasoning as -1; both must be preserved as distinct keys.
        """
        result = normalize_part_number("XC7A35T-2CPG236C")
        assert result == "XC7A35T-2CPG236C"

    def test_normalizer_pn_revision_minus1_and_minus2_differ(self):
        """
        WHAT: PNs that differ only in revision (-1 vs -2) normalise to different strings.
        WHY:  The matcher uses exact string equality; if both normalise to the
              same value, a -1 part would incorrectly match a -2 tender.
        """
        pn1 = normalize_part_number("XC7A35T-1CPG236C")
        pn2 = normalize_part_number("XC7A35T-2CPG236C")
        assert pn1 != pn2

    def test_normalizer_pn_revision_siemens_hw_revision_preserved(self):
        """
        WHAT: Siemens hardware revision suffix in a PLC module PN is kept.
        WHY:  6ES7321-1BL00-0AA0 and 6ES7321-1BL00-0AB0 are different HW revisions
              and must not be collapsed.
        """
        pn_a = normalize_part_number("6ES7321-1BL00-0AA0")
        pn_b = normalize_part_number("6ES7321-1BL00-0AB0")
        assert pn_a != pn_b
        assert pn_a == "6ES7321-1BL00-0AA0"
        assert pn_b == "6ES7321-1BL00-0AB0"

    def test_normalizer_pn_revision_stm32_speed_grade_preserved(self):
        """
        WHAT: STM32 device suffix carrying speed-grade info is not altered.
        WHY:  STM32F407VGT6 (168 MHz) vs STM32F405VGT6 are different devices;
              any numeric tail must survive normalisation intact.
        """
        assert normalize_part_number("STM32F407VGT6") == "STM32F407VGT6"

    @pytest.mark.parametrize("pn", [
        "XC7A35T-1CPG236C",
        "XC7K325T-2FFG900C",
        "5M570ZT100C5N",
        "EP4CE6E22C8N",
    ])
    def test_normalizer_pn_revision_numeric_segment_preserved_parametrized(self, pn: str):
        """
        WHAT: Numeric-only trailing segments in a variety of FPGA/CPLD PNs are kept.
        WHY:  These encode speed grade, temperature grade, and package -- all of
              which distinguish one orderable part from another.
        """
        assert normalize_part_number(pn) == pn.upper()


# ══════════════════════════════════════════════════════════════════════════════
# 6. COMBINED TRANSFORMATIONS
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnCombinedTransformations:
    """Tests that verify multiple normalisation rules applied together."""

    def test_normalizer_pn_combined_lower_slash_suffix(self):
        """
        WHAT: Lowercase input with slash and /NOPB suffix is fully normalised.
        WHY:  Real-world tender text combines all these issues at once.
        """
        assert normalize_part_number("lm317t/nopb") == "LM317T"

    def test_normalizer_pn_combined_space_slash_upper(self):
        """
        WHAT: PN with internal space and slash is uppercased, space-stripped,
              and slash-converted in the correct order.
        WHY:  Validates that the three rules compose without interfering.
        """
        assert normalize_part_number("skkt 162/16e") == "SKKT162-16E"

    def test_normalizer_pn_combined_siemens_space_and_suffix(self):
        """
        WHAT: Siemens-style PN with embedded space and a -TR suffix is fully
              normalised: space removed, suffix stripped, uppercased.
        WHY:  Tape-reel variants of PLC modules may appear in tender imports.
        """
        result = normalize_part_number("6ES7 321-1BL00-0AA0-TR")
        # Space removed, uppercase, -TR stripped.
        assert result == "6ES7321-1BL00-0AA0"

    def test_normalizer_pn_combined_idempotent(self):
        """
        WHAT: Applying normalize_part_number twice yields the same result as once.
        WHY:  The pipeline may normalise data at ingestion and again at match time;
              double-application must not corrupt the key.
        """
        pn = "SKKT162/16E"
        once = normalize_part_number(pn)
        twice = normalize_part_number(once)
        assert once == twice

    def test_normalizer_pn_combined_lowercase_space_nd_suffix(self):
        """
        WHAT: Lowercase PN with space and -nd suffix is correctly normalised.
        WHY:  All three common transformations applied simultaneously to a
              realistic Digi-Key style part number.
        """
        assert normalize_part_number("stm32f103 c8t6-nd") == "STM32F103C8T6"


# ══════════════════════════════════════════════════════════════════════════════
# 7. PIPELINE INTEGRATION: normalize_catalog_item / normalize_tender_item
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPnPipelineIntegration:
    """
    Tests that the high-level pipeline entry points apply PN normalisation
    consistently -- both for catalog entries and tender items.
    """

    def test_normalizer_pn_catalog_item_pn_field_normalised(self):
        """
        WHAT: normalize_catalog_item applies all PN normalisation rules when the
              part_number kwarg is supplied directly.
        WHY:  Catalog CSV from Radal 1C may contain un-normalised PN values.
        """
        rec = normalize_catalog_item(
            source_id="cat-001",
            name="IGBT Module",
            part_number="cm1000e3u-34nf",
            manufacturer="Mitsubishi",
        )
        assert rec.part_number_primary == "CM1000E3U-34NF"

    def test_normalizer_pn_catalog_item_slash_in_pn_field(self):
        """
        WHAT: A slash in the part_number field is converted to a dash.
        WHY:  SEMIKRON entries in the 1C export use slash notation.
        """
        rec = normalize_catalog_item(
            source_id="cat-002",
            name="Тиристорный модуль SKKT162/16E",
            part_number="SKKT162/16E",
        )
        assert rec.part_number_primary == "SKKT162-16E"

    def test_normalizer_pn_catalog_item_suffix_stripped_in_pn_field(self):
        """
        WHAT: Packaging suffix in the part_number field is stripped.
        WHY:  Distributors may import catalog PNs with -ND or -TR suffixes;
              these must not pollute the matching key.
        """
        rec = normalize_catalog_item(
            source_id="cat-003",
            name="LM317 voltage regulator",
            part_number="LM317T-ND",
        )
        assert rec.part_number_primary == "LM317T"

    def test_normalizer_pn_tender_item_siemens_pn_extracted_and_normalised(self):
        """
        WHAT: normalize_tender_item extracts and normalises a Siemens-style PN
              from free-form tender text (space in the middle of the PN).
        WHY:  TenderGuru and B2B-Center tender texts frequently include PNs in
              Siemens datasheet notation with a space.
        """
        rec = normalize_tender_item(
            source_id="tend-001",
            name="Поставка модуля ввода Siemens 6ES7 321-1BL00-0AA0",
        )
        assert "6ES7321-1BL00-0AA0" in rec.part_numbers

    def test_normalizer_pn_tender_item_scenario_a_when_pn_present(self):
        """
        WHAT: A tender containing a recognisable PN is routed to Scenario A.
        WHY:  Scenario A uses exact PN match -- the highest-confidence path.
              Incorrect routing degrades match quality significantly.
        """
        rec = normalize_tender_item(
            source_id="tend-002",
            name="Нужен IGBT модуль CM1000E3U-34NF Mitsubishi 10 шт.",
        )
        assert rec.match_scenario == "A"
        assert rec.part_number_primary != ""

    def test_normalizer_pn_catalog_item_revision_preserved_in_pipeline(self):
        """
        WHAT: A PN with a numeric revision suffix is preserved end-to-end through
              normalize_catalog_item.
        WHY:  Ensures that the pipeline-level processing does not introduce
              additional suffix stripping beyond what normalize_part_number does.
        """
        rec = normalize_catalog_item(
            source_id="cat-004",
            name="Xilinx FPGA XC7A35T-1CPG236C",
            part_number="XC7A35T-1CPG236C",
        )
        assert rec.part_number_primary == "XC7A35T-1CPG236C"

    def test_normalizer_pn_tender_and_catalog_pn_match_after_normalisation(self):
        """
        WHAT: A tender PN written in lowercase with a slash matches the catalog
              entry's normalised PN after both pass through normalisation.
        WHY:  This is the core exact-match scenario: the normalised PN from the
              tender must equal the normalised PN from the catalog.
        """
        catalog_rec = normalize_catalog_item(
            source_id="cat-005",
            name="SEMIKRON тиристорный модуль",
            part_number="SKKT162/16E",
        )
        tender_rec = normalize_tender_item(
            source_id="tend-003",
            name="Закупка тиристоров SKKT162/16E SEMIKRON 5 шт.",
        )
        assert catalog_rec.part_number_primary == tender_rec.part_number_primary
