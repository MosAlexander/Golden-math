"""chart_utils.py — единый источник цветов и Altair-настроек.
Никогда не хардкодить hex-цвета в page-файлах — только импортировать отсюда.
"""
from __future__ import annotations
import altair as alt

# ── UI ──────────────────────────────────────────
PRIMARY_COLOR      = '#FF9800'
PRIMARY_COLOR_FILL = 'rgba(255, 152, 0, 0.18)'  # PRIMARY_COLOR с прозрачностью для заливок
COLOR_CHART_TEXT   = '#E5E7EB'                   # светлый текст на тёмном фоне (Plotly/Altair)

# ── Match decisions ─────────────────────────────
COLOR_AUTO       = '#16a34a'
COLOR_BORDERLINE = '#FACC15'
COLOR_REJECT     = '#EF4444'
COLOR_NEUTRAL    = '#6B7280'

# ── Scenarios ───────────────────────────────────
COLOR_SCENARIO_A = '#3B82F6'
COLOR_SCENARIO_B = '#8B5CF6'
COLOR_SCENARIO_C = '#6B7280'

# ── Semantic aliases ────────────────────────────
COLOR_GOOD    = COLOR_AUTO
COLOR_WARNING = COLOR_BORDERLINE
COLOR_DANGER  = COLOR_REJECT
COLOR_MUTED   = COLOR_NEUTRAL

# ── Matching page extras ────────────────────────
COLOR_BORDERLINE_TEXT    = '#B45309'
COLOR_RELEVANCE_MATCH    = '#8B5CF6'   # alias for COLOR_SCENARIO_B
COLOR_RELEVANCE_STOCK    = '#3B82F6'   # alias for COLOR_SCENARIO_A
COLOR_RELEVANCE_MARGIN   = '#10B981'
COLOR_RELEVANCE_DEADLINE = '#F59E0B'

# ── Palettes ────────────────────────────────────
RAINBOW_PALETTE = ['#8B5CF6', '#3B82F6', '#10B981', '#FACC15', '#F59E0B', '#EF4444']
COMPARE_PALETTE = ['#8B5CF6', '#F59E0B']

# ── Семантические цвета для bar-графиков (категориальное сравнение метрик) ──
# Оба hex уже физически присутствуют в RAINBOW_PALETTE — семантические алиасы.
COLOR_BAR_MONEY = '#8B5CF6'   # фиолетовый — деньги, НМЦ
COLOR_BAR_COUNT = '#F59E0B'   # оранжевый — штуки, количество

# ── Sankey-градиент НМЦ-узлов (порядок сверху вниз: 2–30М₽ → < 100К₽) ──────
NMC_SANKEY_GRADIENT = ["#7C3AED", "#A78BFA", "#C4B5FD", "#EDE9FE"]

# ── Donut ramps по decision ──────────────────────────────────────────────────
DONUT_PALETTES = {
    "borderline": ["#FACC15", "#FBD850", "#FCE285", "#FDEDB8"],
    "auto":       ["#16A34A", "#22C55E", "#4ADE80", "#86EFAC"],
    "reject":     ["#EF4444", "#F87171", "#FCA5A5", "#FECACA"],
}

# ── Sort orders ─────────────────────────────────
DECISION_ORDER = ["auto", "borderline", "reject"]
SCENARIO_ORDER = ["A", "B", "C"]

# ── Altair scales (altair 6.x) ──────────────────
DECISION_SCALE = alt.Scale(
    domain=DECISION_ORDER,
    range=[COLOR_AUTO, COLOR_BORDERLINE, COLOR_REJECT],
)
SCENARIO_SCALE = alt.Scale(
    domain=SCENARIO_ORDER,
    range=[COLOR_SCENARIO_A, COLOR_SCENARIO_B, COLOR_SCENARIO_C],
)
