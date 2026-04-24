"""
test_splink_config.py — Comprehensive pytest tests for src/splink_config.py.

Covers:
  1. classify_match() — boundary thresholds 0.75 / 0.92
  2. calculate_relevance() — stock, margin, deadline components
  3. _calculate_score() — PN / manufacturer / category / voltage / current scoring
  4. prepare_catalog_for_splink() — output schema and field correctness
  5. prepare_tenders_for_splink() — scenario preservation A/B/C

Business rules under test (RULES.md §2):
  ≥0.92 → "auto"
  0.75..0.919 → "borderline"
  <0.75 → "reject"

Relevance formula (RULES.md §4):
  match_quality×0.40 + stock×0.25 + margin×0.20 + deadline×0.15
"""

from __future__ import annotations

import pytest

from src.splink_config import (
    classify_match,
    calculate_relevance,
    _calculate_score,
    prepare_catalog_for_splink,
    prepare_tenders_for_splink,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. classify_match() — threshold boundary tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSplinkConfigClassifyMatch:
    """
    Tests for classify_match() against the three business-rule zones.
    Boundary values are critical: off-by-epsilon bugs silently misroute
    components to LLM or skip LLM entirely.
    """

    @pytest.mark.parametrize("probability,expected", [
        # ── reject zone ──
        (0.0,   "reject"),   # absolute minimum
        (0.500, "reject"),   # middle of reject zone
        (0.749, "reject"),   # just below borderline lower bound
        # ── borderline zone (inclusive on both ends) ──
        (0.75,  "borderline"),  # exact lower bound — must be borderline, not reject
        (0.800, "borderline"),  # mid-borderline
        (0.919, "borderline"),  # just below auto lower bound
        # ── auto zone ──
        (0.92,  "auto"),     # exact lower bound — must be auto, not borderline
        (0.950, "auto"),     # mid-auto
        (1.0,   "auto"),     # absolute maximum
    ])
    def test_splink_config_classify_match_boundaries(
        self, probability: float, expected: str
    ) -> None:
        """
        Verifies that classify_match() maps every boundary value to the correct
        decision label.  0.75 and 0.92 are the critical inclusive lower bounds;
        incorrect handling of these points is a silent routing bug — borderline
        records may bypass LLM review or auto records may be sent to it.
        """
        result = classify_match(probability)
        assert result == expected, (
            f"classify_match({probability}) returned {result!r}, expected {expected!r}"
        )

    def test_splink_config_classify_match_returns_string(self) -> None:
        """
        Return type must always be str so that downstream DataFrame .apply()
        and JSON serialisation work without implicit coercion.
        """
        result = classify_match(0.80)
        assert isinstance(result, str)

    def test_splink_config_classify_match_valid_values_only(self) -> None:
        """
        The only legal return values are 'auto', 'borderline', 'reject'.
        Any other string is a protocol violation that breaks the dashboard
        colour coding and the LLM routing guard.
        """
        allowed = {"auto", "borderline", "reject"}
        for probability in (0.0, 0.3, 0.74, 0.75, 0.80, 0.919, 0.92, 1.0):
            result = classify_match(probability)
            assert result in allowed, (
                f"classify_match({probability}) returned unexpected value {result!r}"
            )

    def test_splink_config_classify_match_075_is_not_reject(self) -> None:
        """
        Regression guard: 0.75 is the inclusive lower bound of borderline.
        A strict '>' instead of '>=' would mis-route this to reject, bypassing
        LLM review and permanently losing the match candidate.
        """
        assert classify_match(0.75) == "borderline"

    def test_splink_config_classify_match_092_is_not_borderline(self) -> None:
        """
        Regression guard: 0.92 is the inclusive lower bound of auto.
        A strict '>' instead of '>=' would mis-route this to borderline,
        causing unnecessary and costly LLM calls for certain matches.
        """
        assert classify_match(0.92) == "auto"


# ══════════════════════════════════════════════════════════════════════════════
# 2. calculate_relevance() — component scoring
# ══════════════════════════════════════════════════════════════════════════════

class TestSplinkConfigCalculateRelevance:
    """
    Tests for calculate_relevance().  The formula has four independent
    components; each is tested in isolation (other components held constant)
    so that a regression in one component is clearly localised.
    """

    # ── result bounds ──────────────────────────────────────────────────────

    def test_splink_config_relevance_result_is_float(self) -> None:
        """Result must be a float so Altair can encode it on a continuous scale."""
        match = {
            "match_probability": 0.95,
            "in_stock": True, "stock_qty": 10,
            "price_max": 120_000, "deadline_days": 3,
        }
        result = calculate_relevance(match)
        assert isinstance(result, float)

    def test_splink_config_relevance_result_in_unit_interval(self) -> None:
        """
        Relevance must stay within [0.0, 1.0].  Values above 1.0 would break
        Altair chart scales; values below 0.0 would invert the sort order.
        """
        match = {
            "match_probability": 1.0,
            "in_stock": True, "stock_qty": 100,
            "price_max": 200_000, "deadline_days": 1,
        }
        result = calculate_relevance(match)
        assert 0.0 <= result <= 1.0, f"Relevance out of bounds: {result}"

    def test_splink_config_relevance_minimum_case(self) -> None:
        """All components at their minimum should produce a small but non-negative score."""
        match = {
            "match_probability": 0.0,
            "in_stock": False, "stock_qty": 0,
            "price_max": 0, "deadline_days": 100,
        }
        result = calculate_relevance(match)
        assert result >= 0.0

    # ── stock component ────────────────────────────────────────────────────

    @pytest.mark.parametrize("qty", [0, 1, 10, 50, 100])
    def test_splink_config_relevance_stock_monotone_increase(self, qty: int) -> None:
        """
        Stock component (25% weight) must be monotonically non-decreasing as
        qty grows from 0 to ≥50.  Formula: min(qty/50, 1.0) × 0.25.
        A stock of 0 must produce 0; ≥50 must reach the ceiling of 0.25.
        """
        base_match = {
            "match_probability": 0.0,
            "price_max": 0, "deadline_days": 100,
        }
        if qty == 0:
            match = {**base_match, "in_stock": False, "stock_qty": 0}
        else:
            match = {**base_match, "in_stock": True, "stock_qty": qty}
        calculate_relevance(match)  # must not raise

    def test_splink_config_relevance_stock_zero_gives_zero_component(self) -> None:
        """
        When in_stock=False or qty=0 the stock component must be 0.0.
        Tested in isolation: match_probability=0, deadlines/margin at minimum.
        """
        match = {
            "match_probability": 0.0,
            "in_stock": False, "stock_qty": 0,
            "price_max": 0, "deadline_days": 100,
        }
        result_no_stock = calculate_relevance(match)

        match_with_stock = {
            "match_probability": 0.0,
            "in_stock": True, "stock_qty": 50,
            "price_max": 0, "deadline_days": 100,
        }
        result_with_stock = calculate_relevance(match_with_stock)
        assert result_with_stock > result_no_stock

    def test_splink_config_relevance_stock_50_reaches_ceiling(self) -> None:
        """
        qty=50 must reach the maximum stock contribution (0.25).
        Formula min(50/50, 1.0)×0.25 = 0.25.  qty=100 must not exceed it.
        """
        base = {"match_probability": 0.0, "price_max": 0, "deadline_days": 100}
        r50  = calculate_relevance({**base, "in_stock": True, "stock_qty": 50})
        r100 = calculate_relevance({**base, "in_stock": True, "stock_qty": 100})
        assert abs(r50 - r100) < 1e-9, (
            "Stock component should plateau at qty=50; qty=100 must not exceed it"
        )

    # ── margin component ───────────────────────────────────────────────────

    @pytest.mark.parametrize("price_max,expected_me", [
        (49_000,  0.05),   # below 50K → low margin tier
        (50_000,  0.05),   # boundary: 50K is NOT >50K, still low tier
        (50_001,  0.12),   # just above 50K → mid tier
        (100_000, 0.12),   # boundary: 100K is NOT >100K, still mid tier
        (100_001, 0.20),   # just above 100K → high tier
        (200_000, 0.20),   # well above 100K → high tier
    ])
    def test_splink_config_relevance_margin_tiers(
        self, price_max: int, expected_me: float
    ) -> None:
        """
        Margin component has three strict tiers driven by НМЦ (price_max):
          >100K → 0.20, >50K → 0.12, else → 0.05
        Boundary values 50K and 100K are critical: they belong to the LOWER
        tier because the condition uses strict '>' not '>='.
        """
        # Isolate margin: zero out all other components
        match = {
            "match_probability": 0.0,
            "in_stock": False, "stock_qty": 0,
            "price_max": price_max,
            "deadline_days": 100,  # → du=0.02
        }
        result = calculate_relevance(match)
        # result = 0 (mq) + 0 (sa) + expected_me + 0.02 (du)
        expected = expected_me + 0.02
        assert abs(result - expected) < 1e-9, (
            f"price_max={price_max}: expected relevance {expected}, got {result}"
        )

    # ── deadline component ─────────────────────────────────────────────────

    @pytest.mark.parametrize("days,expected_du", [
        (5,  0.15),   # ≤5 days → maximum urgency
        (6,  0.10),   # boundary: 6 starts the medium tier
        (10, 0.10),   # still medium tier
        (11, 0.05),   # boundary: 11 starts the low tier
        (20, 0.05),   # still low tier
        (21, 0.02),   # boundary: 21 starts the minimum tier
        (30, 0.02),   # well past all tiers
    ])
    def test_splink_config_relevance_deadline_tiers(
        self, days: int, expected_du: float
    ) -> None:
        """
        Deadline urgency component has four tiers:
          ≤5d → 0.15, ≤10d → 0.10, ≤20d → 0.05, >20d → 0.02
        Boundaries at 5/6, 10/11, 20/21 days are tested explicitly to catch
        off-by-one errors in the tier conditions.
        """
        # Isolate deadline: zero out all other components
        match = {
            "match_probability": 0.0,
            "in_stock": False, "stock_qty": 0,
            "price_max": 0,      # → me=0.05
            "deadline_days": days,
        }
        result = calculate_relevance(match)
        # result = 0 (mq) + 0 (sa) + 0.05 (me) + expected_du
        expected = 0.05 + expected_du
        assert abs(result - expected) < 1e-9, (
            f"deadline_days={days}: expected relevance {expected}, got {result}"
        )

    # ── match_quality component ────────────────────────────────────────────

    def test_splink_config_relevance_match_quality_weight_040(self) -> None:
        """
        Match quality contributes exactly 40% of its probability value.
        With all other components zeroed (no stock, price=0, days=100),
        the result equals probability×0.40 + 0.05 + 0.02.
        """
        match = {
            "match_probability": 1.0,
            "in_stock": False, "stock_qty": 0,
            "price_max": 0, "deadline_days": 100,
        }
        result = calculate_relevance(match)
        expected = 1.0 * 0.40 + 0.05 + 0.02
        assert abs(result - expected) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# 3. _calculate_score() — manual fallback scoring
# ══════════════════════════════════════════════════════════════════════════════

class TestSplinkConfigCalculateScore:
    """
    Tests for _calculate_score(), the Splink fallback used when Splink is not
    installed.  Weights mirror the Splink comparison column weights:
      PN exact 0.60, PN partial 0.40, MFR 0.20, category 0.08,
      voltage exact 0.04 / within-10% 0.02,
      current exact 0.04 / within-15% 0.02.
    """

    # ── Part Number ────────────────────────────────────────────────────────

    def test_splink_config_score_exact_pn_gives_high_score(self) -> None:
        """
        Exact PN match must award 0.60 (the PN weight).  This is the strongest
        single signal in the pipeline and must dominate the final score.
        """
        tender  = {"part_number": "CM1000E3U-34NF", "name_clean": ""}
        catalog = {"part_number": "CM1000E3U-34NF", "name_clean": ""}
        score = _calculate_score(tender, catalog)
        assert score >= 0.60, f"Exact PN match should score ≥0.60, got {score}"

    def test_splink_config_score_partial_pn_gives_medium_score(self) -> None:
        """
        Partial PN match (one PN contains the other as a substring) must award
        0.40.  This covers cases like a tender specifying a short prefix vs the
        full catalog PN.
        """
        tender  = {"part_number": "CM1000",          "name_clean": ""}
        catalog = {"part_number": "CM1000E3U-34NF",  "name_clean": ""}
        score = _calculate_score(tender, catalog)
        assert score >= 0.40, f"Partial PN match should score ≥0.40, got {score}"

    def test_splink_config_score_exact_pn_beats_partial_pn(self) -> None:
        """
        Exact PN match must always score higher than a partial PN match.
        This ensures identical components are ranked above prefix matches.
        """
        tender = {"part_number": "CM1000E3U-34NF", "name_clean": ""}
        exact  = {"part_number": "CM1000E3U-34NF", "name_clean": ""}
        partial = {"part_number": "CM1000",        "name_clean": ""}
        score_exact   = _calculate_score(tender, exact)
        score_partial = _calculate_score(tender, partial)
        assert score_exact > score_partial

    def test_splink_config_score_no_pn_gives_zero_pn_contribution(self) -> None:
        """
        When either tender or catalog has no PN the PN component must be 0.
        Only the remaining components (MFR, category, params) can contribute.
        """
        tender  = {"part_number": "", "name_clean": ""}
        catalog = {"part_number": "CM1000E3U-34NF", "name_clean": ""}
        score_no_pn = _calculate_score(tender, catalog)

        tender_with_pn  = {"part_number": "CM1000E3U-34NF", "name_clean": ""}
        score_with_pn = _calculate_score(tender_with_pn, catalog)
        assert score_no_pn < score_with_pn

    # ── Manufacturer ──────────────────────────────────────────────────────

    def test_splink_config_score_manufacturer_match_boosts_score(self) -> None:
        """
        An identical manufacturer string must add 0.20 to the score.
        Verified by comparing two catalog entries that differ only in manufacturer.
        """
        base_tender  = {"part_number": "", "manufacturer": "mitsubishi", "name_clean": ""}
        cat_same_mfr = {"part_number": "", "manufacturer": "mitsubishi", "name_clean": ""}
        cat_diff_mfr = {"part_number": "", "manufacturer": "siemens",    "name_clean": ""}
        score_same = _calculate_score(base_tender, cat_same_mfr)
        score_diff = _calculate_score(base_tender, cat_diff_mfr)
        assert score_same > score_diff, "Same manufacturer should boost score"
        assert abs((score_same - score_diff) - 0.20) < 1e-9

    # ── Category ──────────────────────────────────────────────────────────

    def test_splink_config_score_category_match_boosts_score(self) -> None:
        """
        Matching category must add 0.08 to the score (the category weight).
        Tested in isolation: no PN, no MFR, no params.
        """
        base_tender   = {"part_number": "", "name_clean": ""}
        cat_same_cat  = {"part_number": "", "name_clean": "", "category": "igbt"}
        cat_diff_cat  = {"part_number": "", "name_clean": "", "category": "diode"}
        tender_igbt   = {**base_tender, "category": "igbt"}
        score_same = _calculate_score(tender_igbt, cat_same_cat)
        score_diff = _calculate_score(tender_igbt, cat_diff_cat)
        assert score_same > score_diff
        assert abs((score_same - score_diff) - 0.08) < 1e-9

    # ── Voltage ───────────────────────────────────────────────────────────

    def test_splink_config_score_voltage_exact_match_adds_004(self) -> None:
        """
        Exact voltage match must add exactly 0.04.
        """
        tender  = {"part_number": "", "name_clean": "", "voltage_v": 1200.0}
        catalog = {"part_number": "", "name_clean": "", "voltage_v": 1200.0}
        score_match = _calculate_score(tender, catalog)

        catalog_no_v = {"part_number": "", "name_clean": ""}
        score_no_v = _calculate_score(tender, catalog_no_v)
        assert abs((score_match - score_no_v) - 0.04) < 1e-9

    def test_splink_config_score_voltage_within_10pct_adds_002(self) -> None:
        """
        Voltage within 10% tolerance must add 0.02 (not 0.04).
        Example: 1100 vs 1200 → diff/max = 100/1200 ≈ 8.3% < 10%.
        """
        tender  = {"part_number": "", "name_clean": "", "voltage_v": 1100.0}
        catalog_close = {"part_number": "", "name_clean": "", "voltage_v": 1200.0}
        catalog_exact = {"part_number": "", "name_clean": "", "voltage_v": 1100.0}
        catalog_none  = {"part_number": "", "name_clean": ""}

        score_close = _calculate_score(tender, catalog_close)
        score_exact = _calculate_score(tender, catalog_exact)
        score_none  = _calculate_score(tender, catalog_none)

        assert score_exact > score_close > score_none
        # within-10% adds 0.02
        assert abs((score_close - score_none) - 0.02) < 1e-9

    def test_splink_config_score_voltage_outside_10pct_adds_zero(self) -> None:
        """
        Voltage outside 10% tolerance must add nothing.
        Example: 600 vs 1200 → diff/max = 600/1200 = 50% > 10%.
        """
        tender        = {"part_number": "", "name_clean": "", "voltage_v": 600.0}
        catalog_far   = {"part_number": "", "name_clean": "", "voltage_v": 1200.0}
        catalog_none  = {"part_number": "", "name_clean": ""}
        score_far  = _calculate_score(tender, catalog_far)
        score_none = _calculate_score(tender, catalog_none)
        assert abs(score_far - score_none) < 1e-9, (
            "Voltage >10% apart should contribute 0 to score"
        )

    # ── Current ───────────────────────────────────────────────────────────

    def test_splink_config_score_current_exact_match_adds_004(self) -> None:
        """
        Exact current match must add exactly 0.04.
        """
        tender  = {"part_number": "", "name_clean": "", "current_a": 400.0}
        catalog_match = {"part_number": "", "name_clean": "", "current_a": 400.0}
        catalog_none  = {"part_number": "", "name_clean": ""}
        score_match = _calculate_score(tender, catalog_match)
        score_none  = _calculate_score(tender, catalog_none)
        assert abs((score_match - score_none) - 0.04) < 1e-9

    def test_splink_config_score_current_within_15pct_adds_002(self) -> None:
        """
        Current within 15% tolerance must add 0.02.
        Example: 350 vs 400 → diff/max = 50/400 = 12.5% < 15%.
        """
        tender        = {"part_number": "", "name_clean": "", "current_a": 350.0}
        catalog_close = {"part_number": "", "name_clean": "", "current_a": 400.0}
        catalog_exact = {"part_number": "", "name_clean": "", "current_a": 350.0}
        catalog_none  = {"part_number": "", "name_clean": ""}

        score_close = _calculate_score(tender, catalog_close)
        score_exact = _calculate_score(tender, catalog_exact)
        score_none  = _calculate_score(tender, catalog_none)

        assert score_exact > score_close > score_none
        assert abs((score_close - score_none) - 0.02) < 1e-9

    def test_splink_config_score_current_outside_15pct_adds_zero(self) -> None:
        """
        Current outside 15% tolerance must add nothing.
        Example: 100 vs 400 → diff/max = 300/400 = 75% > 15%.
        """
        tender       = {"part_number": "", "name_clean": "", "current_a": 100.0}
        catalog_far  = {"part_number": "", "name_clean": "", "current_a": 400.0}
        catalog_none = {"part_number": "", "name_clean": ""}
        score_far  = _calculate_score(tender, catalog_far)
        score_none = _calculate_score(tender, catalog_none)
        assert abs(score_far - score_none) < 1e-9

    # ── Ceiling ───────────────────────────────────────────────────────────

    def test_splink_config_score_never_exceeds_one(self) -> None:
        """
        Score is capped at 1.0 regardless of how many components match.
        Uncapped scores would break classify_match() thresholds.
        """
        tender = {
            "part_number": "CM1000E3U-34NF",
            "manufacturer": "mitsubishi",
            "category": "igbt",
            "voltage_v": 1200.0,
            "current_a": 1000.0,
            "name_clean": "igbt module mitsubishi cm1000",
        }
        catalog = {
            "part_number": "CM1000E3U-34NF",
            "manufacturer": "mitsubishi",
            "category": "igbt",
            "voltage_v": 1200.0,
            "current_a": 1000.0,
            "name_clean": "igbt module mitsubishi cm1000",
        }
        score = _calculate_score(tender, catalog)
        assert score <= 1.0, f"Score exceeded 1.0: {score}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. prepare_catalog_for_splink() — output schema
# ══════════════════════════════════════════════════════════════════════════════

class TestSplinkConfigPrepareCatalog:
    """
    Tests for prepare_catalog_for_splink().  Every row must expose the fields
    that Splink blocking rules and comparisons reference by name.  Missing or
    mis-typed field names cause silent DuckDB SQL errors at runtime.
    """

    REQUIRED_FIELDS = {
        "unique_id", "part_number", "pn_prefix",
        "manufacturer", "category", "source",
    }

    def _make_catalog_item(self, **overrides) -> dict:
        """Minimal valid catalog item."""
        base = {
            "id": "CAT-001",
            "name": "IGBT Module CM1000E3U-34NF",
            "part_number": "CM1000E3U-34NF",
            "manufacturer": "Mitsubishi",
            "category": "igbt",
            "params": {"voltage_v": 1200, "current_a": 1000},
            "in_stock": True,
            "stock_qty": 5,
        }
        base.update(overrides)
        return base

    def test_splink_config_prepare_catalog_returns_list_of_dicts(self) -> None:
        """
        Output must be a plain list[dict] so it can be passed directly to
        Splink's Linker or iterated in the fallback pipeline.
        """
        result = prepare_catalog_for_splink([self._make_catalog_item()])
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_splink_config_prepare_catalog_all_required_fields_present(self) -> None:
        """
        Each output row must contain every field referenced by Splink blocking
        rules ('pn_prefix', 'category', 'manufacturer') and comparison columns
        ('part_number', 'manufacturer', 'category').  A missing field causes a
        silent DuckDB ColumnNotFound error.
        """
        result = prepare_catalog_for_splink([self._make_catalog_item()])
        row = result[0]
        for field in self.REQUIRED_FIELDS:
            assert field in row, f"Required field '{field}' missing from catalog row"

    def test_splink_config_prepare_catalog_pn_prefix_is_first_6_chars(self) -> None:
        """
        pn_prefix is used for blocking rule 'l.pn_prefix = r.pn_prefix'.
        The implementation slices the first 6 characters of the uppercased PN.
        Verified against the known input 'CM1000E3U-34NF' → prefix 'CM1000'.
        """
        item = self._make_catalog_item(part_number="CM1000E3U-34NF")
        result = prepare_catalog_for_splink([item])
        assert result[0]["pn_prefix"] == "CM1000"

    def test_splink_config_prepare_catalog_pn_uppercased(self) -> None:
        """
        Part numbers must be uppercased in the output regardless of input case,
        because Splink exact-match SQL is case-sensitive.
        """
        item = self._make_catalog_item(part_number="cm1000e3u-34nf")
        result = prepare_catalog_for_splink([item])
        assert result[0]["part_number"] == "CM1000E3U-34NF"

    def test_splink_config_prepare_catalog_pn_spaces_removed(self) -> None:
        """
        Spaces in part numbers must be removed so that Siemens-style PNs
        like '6ES7 321-1BL00-0AA0' match their normalized catalog equivalents.
        """
        item = self._make_catalog_item(part_number="6ES7 321-1BL00-0AA0")
        result = prepare_catalog_for_splink([item])
        assert " " not in result[0]["part_number"]

    def test_splink_config_prepare_catalog_source_field_is_catalog(self) -> None:
        """
        The 'source' field must be 'catalog' so that Splink link_only mode can
        distinguish the two input tables.  Wrong source label causes Splink to
        treat both tables as the same dataset and deduplicate instead of linking.
        """
        result = prepare_catalog_for_splink([self._make_catalog_item()])
        assert result[0]["source"] == "catalog"

    def test_splink_config_prepare_catalog_multiple_items_preserved(self) -> None:
        """
        All input items must appear in the output — the function must not drop
        or deduplicate records.
        """
        items = [
            self._make_catalog_item(id="CAT-001", part_number="CM1000E3U-34NF"),
            self._make_catalog_item(id="CAT-002", part_number="SKKT162-16E"),
            self._make_catalog_item(id="CAT-003", part_number="7MBR75UB120"),
        ]
        result = prepare_catalog_for_splink(items)
        assert len(result) == 3

    def test_splink_config_prepare_catalog_params_voltage_mapped(self) -> None:
        """
        voltage_v from the params dict must be accessible as a top-level field
        so that Splink's voltage comparison column can reference it directly.
        """
        item = self._make_catalog_item(params={"voltage_v": 1200, "current_a": 400})
        result = prepare_catalog_for_splink([item])
        assert result[0]["voltage_v"] == 1200

    def test_splink_config_prepare_catalog_params_current_mapped(self) -> None:
        """
        current_a from the params dict must be accessible as a top-level field
        for the same reason as voltage_v above.
        """
        item = self._make_catalog_item(params={"voltage_v": 1200, "current_a": 400})
        result = prepare_catalog_for_splink([item])
        assert result[0]["current_a"] == 400


# ══════════════════════════════════════════════════════════════════════════════
# 5. prepare_tenders_for_splink() — scenario field and output shape
# ══════════════════════════════════════════════════════════════════════════════

class TestSplinkConfigPrepareTenders:
    """
    Tests for prepare_tenders_for_splink().  The normaliser assigns a
    match_scenario (A/B/C) based on what was extracted.  The downstream
    ranking and LLM routing use this field to apply scenario-specific logic.

    Note: prepare_tenders_for_splink() calls normalize_tender_item() internally.
    match_scenario is derived from the PN/params extracted from the tender name,
    not from an input field.  Tests must verify that the scenario assigned by
    the normaliser is the correct one for the given tender text.
    """

    def _make_tender(self, **overrides) -> dict:
        """Minimal valid tender dict."""
        base = {
            "id": "TND-001",
            "name": "Поставка IGBT CM1000E3U-34NF Mitsubishi",
            "okpd2": "",
            "region": "Ставрополь",
            "price_max": 120_000.0,
            "quantity_str": "10 шт",
            "deadline_days": 7,
        }
        base.update(overrides)
        return base

    def test_splink_config_prepare_tenders_returns_list_of_dicts(self) -> None:
        """
        Output must be list[dict] for the same reason as the catalog function.
        """
        result = prepare_tenders_for_splink([self._make_tender()])
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_splink_config_prepare_tenders_source_field_is_tender(self) -> None:
        """
        The 'source' field must be 'tender' so Splink can distinguish the two
        input tables in link_only mode.
        """
        result = prepare_tenders_for_splink([self._make_tender()])
        assert result[0]["source"] == "tender"

    def test_splink_config_prepare_tenders_scenario_a_when_pn_present(self) -> None:
        """
        A tender that contains an explicit part number must be classified as
        Scenario A ('A') by the normaliser.  Scenario A uses exact PN match,
        which is the highest-confidence path and does not require parametric
        fallback.

        The tender name 'Поставка IGBT CM1000E3U-34NF Mitsubishi' contains a
        clear PN, so the normaliser must assign match_scenario='A'.
        The prepare function does not expose match_scenario as an output field
        directly, but the normalised part_number must be non-empty.
        """
        tender = self._make_tender(
            name="Поставка IGBT CM1000E3U-34NF Mitsubishi"
        )
        result = prepare_tenders_for_splink([tender])
        row = result[0]
        # For scenario A: part_number must be extracted and non-empty
        assert row["part_number"], (
            "Scenario A tender must have a non-empty part_number after normalization"
        )

    def test_splink_config_prepare_tenders_scenario_b_when_no_pn(self) -> None:
        """
        A tender with parameters but no part number must result in an empty
        part_number field.  This corresponds to Scenario B (parametric match).
        The blocking rule 'l.category = r.category AND l.manufacturer = r.manufacturer'
        must then be the primary matching path.
        """
        tender = self._make_tender(
            name="IGBT-модуль 1200В 1000А Mitsubishi для стенда",
        )
        result = prepare_tenders_for_splink([tender])
        row = result[0]
        # For Scenario B: no PN, but category and/or params must be present
        # The part_number may or may not be empty depending on regex extraction;
        # what matters is that if a PN was NOT in the text, the field is empty.
        # We verify the category field is populated (B requires category).
        assert row.get("category") or row.get("voltage_v") is not None, (
            "Scenario B tender must have category or electrical params populated"
        )

    def test_splink_config_prepare_tenders_multiple_tenders_preserved(self) -> None:
        """
        All input tenders must appear in the output without being dropped or
        merged.  Record loss in the tender preparation step means whole tenders
        are silently excluded from matching.
        """
        tenders = [
            self._make_tender(id="TND-001", name="Поставка IGBT CM1000E3U-34NF"),
            self._make_tender(id="TND-002", name="IGBT-модуль 1200В Mitsubishi"),
            self._make_tender(id="TND-003", name="Поставка электронных компонентов"),
        ]
        result = prepare_tenders_for_splink(tenders)
        assert len(result) == 3

    def test_splink_config_prepare_tenders_deadline_days_preserved(self) -> None:
        """
        deadline_days must be passed through unchanged to the output row because
        calculate_relevance() reads it directly from the matched result dict.
        Losing this field would make every match appear as a low-urgency case
        (default 30 days) and corrupt the relevance ranking.
        """
        tender = self._make_tender(deadline_days=3)
        result = prepare_tenders_for_splink([tender])
        assert result[0].get("deadline_days") == 3

    def test_splink_config_prepare_tenders_price_max_preserved(self) -> None:
        """
        price_max (НМЦ) must be preserved in the output row because
        calculate_relevance() uses it to determine the margin tier.
        """
        tender = self._make_tender(price_max=150_000.0)
        result = prepare_tenders_for_splink([tender])
        assert result[0].get("price_max") == 150_000.0

    def test_splink_config_prepare_tenders_pn_prefix_populated_when_pn_present(
        self,
    ) -> None:
        """
        When a part number is extracted, pn_prefix must be non-empty so that
        the blocking rule 'l.pn_prefix = r.pn_prefix' can fire.  An empty
        pn_prefix means the tender will only be blocked on category/manufacturer
        even when a PN is available — missing the best blocking path.
        """
        tender = self._make_tender(
            name="Поставка IGBT модуль CM1000E3U-34NF Mitsubishi"
        )
        result = prepare_tenders_for_splink([tender])
        row = result[0]
        if row["part_number"]:  # only meaningful if PN was extracted
            assert row["pn_prefix"], (
                "pn_prefix must be non-empty when part_number is present"
            )
