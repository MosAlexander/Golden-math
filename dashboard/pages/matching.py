from __future__ import annotations

import json
from datetime import datetime

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import logging

from dashboard.chart_utils import (
    COLOR_AUTO,
    COLOR_BORDERLINE,
    COLOR_REJECT,
    COLOR_RELEVANCE_MATCH,
    COLOR_RELEVANCE_STOCK,
    COLOR_RELEVANCE_MARGIN,
    COLOR_RELEVANCE_DEADLINE,
)

logger = logging.getLogger(__name__)
from dashboard.data_utils import (
    get_run_metadata,
    load_catalog,
    load_pipeline_results,
    load_tenders,
)


# ── Format helper ─────────────────────────────────────────────────────────────

def _format_nmc(v: float | None) -> str:
    if not v or v == 0:
        return "—"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f} М ₽"
    if v >= 1_000:
        return f"{v / 1_000:.0f} К ₽"
    return f"{v:.0f} ₽"


@st.cache_data
def _get_scenario(tender_id: str, tender_name: str) -> str:
    from src.normalizer_electronics import normalize_tender_item
    return normalize_tender_item(tender_id, tender_name).match_scenario


# ── Radar helpers ─────────────────────────────────────────────────────────────

@st.cache_data
def _compute_radar_axes(
    tender_id: str,
    tender_name: str,
    catalog_id: str,
) -> dict[str, float]:
    """Возвращает {axis: 0.0 or 1.0} для 5 осей радара."""
    from src.normalizer_electronics import normalize_tender_item

    catalog_df = load_catalog()
    cat = catalog_df[catalog_df["id"] == catalog_id].iloc[0].to_dict()

    # params может быть строкой JSON в зависимости от источника
    cat_params = cat.get("params", {})
    if isinstance(cat_params, str):
        try:
            cat_params = json.loads(cat_params)
        except (ValueError, TypeError):
            cat_params = {}

    rec = normalize_tender_item(tender_id, tender_name)

    t_pn = rec.part_number_primary or ""
    c_pn = (cat.get("part_number") or "").upper().replace(" ", "")
    pn_match = bool(t_pn) and t_pn == c_pn

    t_mfr = (rec.manufacturer or "").lower()
    c_mfr = (cat.get("manufacturer") or "").lower()
    mfr_match = bool(t_mfr) and bool(c_mfr) and t_mfr == c_mfr

    cat_match = bool(rec.category) and rec.category == cat.get("category", "")

    t_v = rec.params.get("voltage_v")
    c_v = cat_params.get("voltage_v")
    v_match = t_v is not None and c_v is not None and t_v == c_v

    t_a = rec.params.get("current_a")
    c_a = cat_params.get("current_a")
    a_match = t_a is not None and c_a is not None and t_a == c_a

    return {
        "Part Number":  1.0 if pn_match  else 0.0,
        "Производитель": 1.0 if mfr_match else 0.0,
        "Категория":    1.0 if cat_match  else 0.0,
        "Напряжение":   1.0 if v_match    else 0.0,
        "Ток":          1.0 if a_match    else 0.0,
    }


def _build_radar_chart(axes: dict[str, float]) -> go.Figure:
    categories = list(axes.keys())
    values     = list(axes.values())

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor="rgba(255, 152, 0, 0.18)",
        line=dict(color="#FF9800", width=1.5),
        marker=dict(size=8, color="#FF9800"),
        hovertemplate="<b>%{theta}</b><br>Совпало: %{r:.0f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                showticklabels=False,
                gridcolor="rgba(255, 255, 255, 0.1)",
                linecolor="rgba(255, 255, 255, 0.1)",
            ),
            angularaxis=dict(
                gridcolor="rgba(255, 255, 255, 0.1)",
                linecolor="rgba(255, 255, 255, 0.1)",
                tickfont=dict(size=11, color="#E5E7EB"),
            ),
            bgcolor="rgba(0, 0, 0, 0)",
        ),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=40, t=20, b=20),
        height=340,
        showlegend=False,
        font=dict(family="Source Sans Pro, sans-serif"),
    )
    return fig


def _get_radar_insights(
    axes: dict[str, float],
    catalog_row: dict,
) -> list[str]:
    matched_count = sum(1 for v in axes.values() if v == 1.0)
    total = len(axes)
    lines: list[str] = []

    if matched_count == total:
        lines.append(f":primary[**Все {total} атрибутов совпали**] — идеальный матч по всем осям.")
    else:
        lines.append(f":primary[**Совпало {matched_count} из {total} атрибутов**] — параметрический матч.")

    if axes["Part Number"] == 1.0:
        pn = catalog_row.get("part_number", "—")
        lines.append(f":primary[**PN exact match**]: {pn} в тендере точно совпадает с каталогом.")
    else:
        lines.append(":primary[**Part number отсутствует**] в тексте тендера — самый сильный сигнал недоступен.")

    if axes["Производитель"] == 1.0:
        mfr = catalog_row.get("manufacturer", "—")
        lines.append(f":primary[**Производитель подтверждён**]: {mfr} совпадает.")
    else:
        lines.append(":primary[**Производитель не указан**] — тендер открытый по бренду.")

    if axes["Напряжение"] == 1.0 and axes["Ток"] == 1.0:
        v = catalog_row.get("params", {})
        if isinstance(v, str):
            v = {}
        lines.append(
            f":primary[**Параметры в точности**]: "
            f"{v.get('voltage_v', '—')}V × {v.get('current_a', '—')}A."
        )
    elif axes["Напряжение"] == 1.0 or axes["Ток"] == 1.0:
        lines.append(":primary[**Параметры частично совпадают**] — не все характеристики извлечены.")

    return lines


# ── Waterfall helpers ─────────────────────────────────────────────────────────

@st.cache_data
def _decompose_score(
    tender_id: str,
    tender_name: str,
    catalog_id: str,
) -> list[dict]:
    """6 шагов вклада в итоговый score.

    Логика ДОЛЖНА совпадать с _calculate_score() из splink_config.py.
    Если splink_config меняется — этот хелпер тоже нужно обновлять.
    Отличие от промта: добавлен PN+MFR bonus (+0.05) из реальной реализации.
    """
    from src.normalizer_electronics import normalize_tender_item

    catalog_df = load_catalog()
    cat = catalog_df[catalog_df["id"] == catalog_id].iloc[0].to_dict()

    cat_params = cat.get("params", {})
    if isinstance(cat_params, str):
        try:
            cat_params = json.loads(cat_params)
        except (ValueError, TypeError):
            cat_params = {}

    rec = normalize_tender_item(tender_id, tender_name)

    contributions: list[dict] = []
    cumulative = 0.0

    # 1. PN (60%)
    t_pn = rec.part_number_primary or ""
    c_pn = (cat.get("part_number") or "").upper().replace(" ", "")
    if t_pn and c_pn:
        if t_pn == c_pn:
            v = 0.60
        elif t_pn in c_pn or c_pn in t_pn:
            v = 0.40
        else:
            v = 0.0
    else:
        v = 0.0
    cumulative += v
    contributions.append({"step": "PN", "value": v, "cumulative": cumulative})

    # 2. MFR (20%)
    t_mfr = (rec.manufacturer or "").lower()
    c_mfr = (cat.get("manufacturer") or "").lower()
    v = 0.20 if t_mfr and c_mfr and t_mfr == c_mfr else 0.0
    cumulative += v
    contributions.append({"step": "MFR", "value": v, "cumulative": cumulative})

    # 3. PN+MFR bonus (5%) — архитектурный контракт из DECISIONS.md
    exact_pn = t_pn and c_pn and t_pn == c_pn
    exact_mfr = t_mfr and c_mfr and t_mfr == c_mfr
    v = 0.05 if (exact_pn and exact_mfr) else 0.0
    cumulative += v
    contributions.append({"step": "Бонус", "value": v, "cumulative": cumulative})

    # 4. Категория (8%)
    v = 0.08 if rec.category and rec.category == cat.get("category", "") else 0.0
    cumulative += v
    contributions.append({"step": "Кат.", "value": v, "cumulative": cumulative})

    # 5. Напряжение (4%)
    t_v = rec.params.get("voltage_v")
    c_v = cat_params.get("voltage_v")
    if t_v and c_v:
        if t_v == c_v:
            v = 0.04
        elif abs(t_v - c_v) / max(t_v, c_v, 1) < 0.1:
            v = 0.02
        else:
            v = 0.0
    else:
        v = 0.0
    cumulative += v
    contributions.append({"step": "V", "value": v, "cumulative": cumulative})

    # 6. Ток (4%)
    t_a = rec.params.get("current_a")
    c_a = cat_params.get("current_a")
    if t_a and c_a:
        if t_a == c_a:
            v = 0.04
        elif abs(t_a - c_a) / max(t_a, c_a, 1) < 0.15:
            v = 0.02
        else:
            v = 0.0
    else:
        v = 0.0
    cumulative += v
    contributions.append({"step": "A", "value": v, "cumulative": cumulative})

    # 7. Описание (4%)
    t_name = (rec.name_clean or "").lower()
    c_name = (cat.get("name") or "").lower()
    if t_name and c_name:
        t_words = set(t_name.split())
        c_words = set(c_name.split())
        if t_words and c_words:
            overlap = len(t_words & c_words) / max(len(t_words), len(c_words))
            v = 0.04 * overlap
        else:
            v = 0.0
    else:
        v = 0.0
    cumulative += v
    contributions.append({"step": "Описание", "value": v, "cumulative": cumulative})

    return contributions


def _build_waterfall_chart(contributions: list[dict], match: dict) -> go.Figure:
    decision = match.get("decision", "reject")
    prob = float(match.get("match_probability", 0))

    if decision == "auto":
        total_color = "#16a34a"
    elif decision == "borderline":
        total_color = "#FACC15"
    else:
        total_color = "#EF4444"

    x_values  = [c["step"] for c in contributions] + ["Итог"]
    y_values  = [c["value"] for c in contributions] + [prob]
    measures  = ["relative"] * len(contributions) + ["total"]
    text_vals = [
        f"+{c['value']:.2f}" if c["value"] > 0 else "0.00"
        for c in contributions
    ] + [f"{prob:.2f}"]

    fig = go.Figure(go.Waterfall(
        x=x_values,
        y=y_values,
        measure=measures,
        text=text_vals,
        textposition="outside",
        connector=dict(
            line=dict(color="rgba(255, 255, 255, 0.25)", width=1, dash="dot"),
        ),
        increasing=dict(marker=dict(color="#8B5CF6", line=dict(width=0))),
        decreasing=dict(marker=dict(color="#8B5CF6", line=dict(width=0))),
        totals=dict(marker=dict(color=total_color, line=dict(width=0))),
        hovertemplate="<b>%{x}</b><br>Вклад: %{y:+.3f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=20, t=30, b=40),
        height=340,
        xaxis=dict(
            tickfont=dict(size=11, color="#E5E7EB"),
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            range=[0, 1.10],
            tickformat=".2f",
            tickfont=dict(size=10, color="#9CA3AF"),
            gridcolor="rgba(255, 255, 255, 0.06)",
            zeroline=False,
        ),
        font=dict(family="Source Sans Pro, sans-serif"),
        showlegend=False,
    )
    return fig


def _get_waterfall_insights(contributions: list[dict], match: dict) -> list[str]:
    decision = match.get("decision", "reject")
    prob = float(match.get("match_probability", 0))

    pn_v    = contributions[0]["value"]
    mfr_v   = contributions[1]["value"]
    bonus_v = contributions[2]["value"]
    param_v = sum(c["value"] for c in contributions[3:6])  # Кат + V + A
    name_v  = contributions[6]["value"]

    lines: list[str] = []

    if pn_v >= 0.60:
        lines.append(":primary[**PN дал +0.60**] — это решающий фактор, без него матч был бы borderline.")
    elif pn_v >= 0.40:
        lines.append(f":primary[**PN частичный +{pn_v:.2f}**] — нет точного PN, но описание совпадает с каталогом.")
    else:
        lines.append(":primary[**Part number не извлечён**] — параметрический матч без PN.")

    if mfr_v >= 0.20:
        lines.append(":primary[**MFR подтверждение +0.20**] — производитель прямо назван в ТЗ.")
    else:
        lines.append(":primary[**MFR не определён**] — это главная причина неполной уверенности.")

    total_extra = param_v + name_v
    if total_extra >= 0.10:
        lines.append(f":primary[**Параметрика +{total_extra:.2f}**] — категория, напряжение, ток поддерживают матч.")
    else:
        lines.append(f":primary[**Параметрика +{total_extra:.2f}**] — слабый сигнал.")

    if decision == "auto":
        margin = prob - 0.92
        lines.append(f":primary[**Уверенно в auto-зоне**] — порог пройден с запасом {margin * 100:.0f}%.")
    elif decision == "borderline":
        gap = 0.92 - prob
        lines.append(f":primary[**Не дотянули {gap * 100:.0f}%**] до auto-зоны (≥0.92).")
    else:
        lines.append(":primary[**Score ниже порога**] — матч не подтверждён.")

    return lines


# ── Zone indicator ────────────────────────────────────────────────────────────

def _render_zone_indicator(match: dict) -> None:
    prob = float(match.get("match_probability", 0))

    df = pd.DataFrame([
        {"zone": "reject",     "width": 0.75, "order": 0},
        {"zone": "borderline", "width": 0.17, "order": 1},
        {"zone": "auto",       "width": 0.08, "order": 2},
    ])
    bar = (
        alt.Chart(df)
        .mark_bar(height=8)
        .encode(
            x=alt.X("width:Q", stack="zero", axis=None, scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "zone:N",
                scale=alt.Scale(
                    domain=["reject", "borderline", "auto"],
                    range=["#EF4444", "#FACC15", "#16a34a"],
                ),
                legend=None,
            ),
            order="order:Q",
        )
    )
    marker = (
        alt.Chart(pd.DataFrame([{"x": prob}]))
        .mark_rule(color="#FF9800", strokeWidth=2)
        .encode(x="x:Q")
    )
    chart = (bar + marker).properties(width="container", height=20)
    st.altair_chart(chart, use_container_width=True)

    cols = st.columns([33, 33, 34])
    cols[0].caption("reject")
    cols[1].caption("borderline")
    cols[2].caption("auto")


# ── Relevance decomposition ──────────────────────────────────────────────────

@st.cache_data
def _decompose_relevance(
    match_probability: float,
    in_stock: bool,
    stock_qty: int,
    price_max: float | None,
    deadline_days: int | None,
) -> dict[str, dict]:
    """Декомпозиция итогового relevance на 4 компонента.

    Логика ДОЛЖНА совпадать с calculate_relevance() из splink_config.py.
    Если splink_config меняется — этот хелпер тоже обновлять.

    Возвращает {component: {"value": float, "raw": float, "weight": float}}
    где value = вклад после умножения на вес, raw = value / weight (0..1).
    """
    from src.splink_config import calculate_relevance

    # Match quality (40%)
    mq_value = match_probability * 0.40

    # Stock availability (25%)
    if in_stock and stock_qty > 0:
        stock_score = min(stock_qty / 50, 1.0)
        sa_value = stock_score * 0.25
    else:
        stock_score = 0.0
        sa_value = 0.0

    # Margin estimate (20%)
    price = price_max or 0
    if price > 100_000:
        me_value = 0.20
    elif price > 50_000:
        me_value = 0.12
    else:
        me_value = 0.05

    # Deadline urgency (15%)
    days = deadline_days if deadline_days is not None else 30
    if days <= 5:
        du_value = 0.15
    elif days <= 10:
        du_value = 0.10
    elif days <= 20:
        du_value = 0.05
    else:
        du_value = 0.02

    result = {
        "match_quality": {"value": mq_value,  "raw": match_probability, "weight": 0.40},
        "stock":         {"value": sa_value,   "raw": stock_score,       "weight": 0.25},
        "margin":        {"value": me_value,   "raw": me_value / 0.20,   "weight": 0.20},
        "deadline":      {"value": du_value,   "raw": du_value / 0.15,   "weight": 0.15},
    }

    # Sanity-check: сумма компонентов должна совпадать с calculate_relevance
    match_dict = {
        "match_probability": match_probability,
        "in_stock": in_stock,
        "stock_qty": stock_qty,
        "price_max": price_max,
        "deadline_days": deadline_days,
    }
    expected = calculate_relevance(match_dict)
    actual = sum(c["value"] for c in result.values())
    if abs(actual - expected) > 1e-9:
        logger.warning(
            "_decompose_relevance drift: computed=%.10f expected=%.10f",
            actual, expected,
        )

    return result


# ── Block 1: match card ───────────────────────────────────────────────────────

def _render_match_card(tender_row: dict, catalog_row: dict, best_match: dict) -> None:
    with st.container(border=True):
        st.markdown("#### :primary[:material/article:] Карточка матча")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.caption("Тендер")
            st.markdown(f"**{tender_row.get('id', '—')}**")
            deadline_days = int(tender_row.get("deadline_days", 0) or 0)
            nmc_str = _format_nmc(tender_row.get("price_max"))
            deadline_str = (
                f":red[Дедлайн {deadline_days} д]"
                if deadline_days <= 7
                else f"Дедлайн {deadline_days} д"
            )
            st.markdown(
                f"{tender_row.get('region', '—')}  \n"
                f"{nmc_str} · {deadline_str}"
            )

        with col2:
            st.caption("Лучший SKU")
            st.markdown(f"**{catalog_row.get('id', '—')}**")
            in_stock  = catalog_row.get("in_stock", False)
            stock_qty = int(catalog_row.get("stock_qty", 0) or 0)
            stock_text = (
                f":green[{stock_qty} шт на складе]"
                if in_stock and stock_qty > 0
                else "—"
            )
            st.markdown(
                f"{catalog_row.get('manufacturer', '—')} · "
                f"{catalog_row.get('category', '—')}  \n{stock_text}"
            )

        with col3:
            st.caption("Match probability")
            prob     = float(best_match.get("match_probability", 0))
            decision = best_match.get("decision", "reject")
            scenario = best_match.get("match_scenario") or _get_scenario(
                tender_row.get("id", ""), tender_row.get("name", "")
            )
            prob_pct = int(prob * 100)

            if decision == "auto":
                st.markdown(f"### :green[**{prob_pct}%**]")
                st.markdown(f":green-badge[AUTO · сценарий {scenario}]")
            elif decision == "borderline":
                st.markdown(f"### :yellow[**{prob_pct}%**]")
                st.markdown(f":yellow-badge[BORDERLINE · сценарий {scenario}]")
            else:
                st.markdown(f"### :red[**{prob_pct}%**]")
                st.markdown(f":red[**REJECT · сценарий {scenario}**]")

        with col4:
            st.caption("Relevance")
            relevance = float(best_match.get("relevance", 0))
            st.markdown(f"### :primary[**{relevance:.2f}**]")
            st.caption("Приоритет в ленте")


# ── Empty state ───────────────────────────────────────────────────────────────

def _render_empty_state() -> None:
    with st.container(border=True):
        st.markdown("#### :primary[:material/info:] Тендер не выбран")
        st.markdown(
            "Чтобы увидеть детальный разбор матча, выберите тендер на странице "
            "**Лента тендеров**."
        )
        st.page_link(
            "pages/tender_feed.py",
            label="Перейти в Ленту тендеров",
            icon=":material/list_alt:",
        )


# ── Page ──────────────────────────────────────────────────────────────────────

tender_id = st.session_state.get("selected_tender_id")

if tender_id is None:
    st.markdown("## :primary[:material/insights:] Матчинг")
    _render_empty_state()
    st.stop()

results  = load_pipeline_results()
tenders  = load_tenders()
catalog  = load_catalog()
metadata = get_run_metadata()

tender_matches = results[results["tender_id"] == tender_id]
if tender_matches.empty:
    st.markdown("## :primary[:material/insights:] Матчинг")
    st.warning("Для этого тендера не найдено совпадений с каталогом.")
    st.stop()

best_match = tender_matches.loc[tender_matches["relevance"].idxmax()].to_dict()

tender_rows = tenders[tenders["id"] == tender_id]
if tender_rows.empty:
    st.markdown("## :primary[:material/insights:] Матчинг")
    st.warning("Тендер не найден в данных.")
    st.stop()

tender_row  = tender_rows.iloc[0].to_dict()
catalog_row = catalog[catalog["id"] == best_match["catalog_id"]].iloc[0].to_dict()

# ── Заголовок ─────────────────────────────────────────────────────────────────
st.markdown("## :primary[:material/insights:] Матчинг")

ts_iso = metadata.get("timestamp", "")
try:
    if ts_iso and ts_iso != "—":
        dt = datetime.fromisoformat(ts_iso)
        ts_human = dt.strftime("%d.%m.%Y, %H:%M")
        caption_text = (
            f"Детальный разбор выбранного матча и принятие решения · "
            f"Прогон пайплайна: {ts_human}"
        )
    else:
        caption_text = "Детальный разбор выбранного матча и принятие решения"
except (ValueError, TypeError):
    caption_text = "Детальный разбор выбранного матча и принятие решения"

st.caption(caption_text)

# Предвычисляем данные для блоков 2-3
prob_pct      = int(float(best_match.get("match_probability", 0)) * 100)
radar_axes    = _compute_radar_axes(tender_id, tender_row.get("name", ""), best_match["catalog_id"])
contributions = _decompose_score(tender_id, tender_row.get("name", ""), best_match["catalog_id"])

# ── Блок 1: карточка матча ────────────────────────────────────────────────────
_render_match_card(tender_row, catalog_row, best_match)

# ── Блок 2: радар + insights ──────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/track_changes:] Что совпало в товаре")
    chart_col, insights_col = st.columns([2, 1])

    with chart_col:
        radar_fig = _build_radar_chart(radar_axes)
        st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})

    with insights_col:
        st.caption("KEY INSIGHTS")
        for line in _get_radar_insights(radar_axes, catalog_row):
            st.markdown(line)

# ── Блок 3: waterfall + insights + зональная шкала ───────────────────────────
with st.container(border=True):
    st.markdown(f"#### :primary[:material/stairs:] Из чего сложилась уверенность {prob_pct}%")
    chart_col, insights_col = st.columns([2, 1])

    with chart_col:
        wf_fig = _build_waterfall_chart(contributions, best_match)
        st.plotly_chart(wf_fig, use_container_width=True, config={"displayModeBar": False})

    with insights_col:
        st.caption("KEY INSIGHTS")
        for line in _get_waterfall_insights(contributions, best_match):
            st.markdown(line)

        st.divider()
        st.caption("Зона уверенности")
        _render_zone_indicator(best_match)

# ── Блок 4: LLM-плейсхолдер (только borderline) ──────────────────────────────
if best_match.get("decision") == "borderline":
    with st.container(border=True):
        st.markdown("#### :primary[:material/auto_awesome:] Мнение LLM-эксперта")
        info_col, btn_col = st.columns([4, 1])
        with info_col:
            st.markdown(
                "Этот матч находится в borderline-зоне (0.75–0.92) — "
                "движок не уверен достаточно для авто-решения."
            )
            st.caption(
                "В production-версии GigaChat / YandexGPT дают вердикт за ~2 секунды. "
                "Активация запланирована в Gate 8."
            )
        with btn_col:
            st.button(
                "Запросить анализ",
                disabled=True,
                key="llm_request_disabled",
                help="Активируется в Gate 8 — LLM-judge",
            )

# ── Блок 5: relevance breakdown ───────────────────────────────────────────────
relevance      = float(best_match.get("relevance", 0))
in_stock_bm    = bool(best_match.get("in_stock", False))
stock_qty_bm   = int(best_match.get("stock_qty", 0) or 0)
price_max_bm   = best_match.get("price_max")
deadline_bm    = best_match.get("deadline_days")
deadline_int   = int(deadline_bm) if deadline_bm is not None else None

comp = _decompose_relevance(
    match_probability=float(best_match.get("match_probability", 0)),
    in_stock=in_stock_bm,
    stock_qty=stock_qty_bm,
    price_max=float(price_max_bm) if price_max_bm is not None else None,
    deadline_days=deadline_int,
)

with st.container(border=True):
    header_left, header_right = st.columns([2, 1])
    with header_left:
        st.markdown("#### :primary[:material/leaderboard:] Стоит ли брать в работу")
    with header_right:
        st.markdown(f"### :primary[**{relevance:.2f}**]")
        st.caption("Приоритет в ленте")

    # Segmented bar
    breakdown_df = pd.DataFrame([
        {"component": "Match",    "value": comp["match_quality"]["value"], "order": 1, "color": COLOR_RELEVANCE_MATCH},
        {"component": "Stock",    "value": comp["stock"]["value"],         "order": 2, "color": COLOR_RELEVANCE_STOCK},
        {"component": "Margin",   "value": comp["margin"]["value"],        "order": 3, "color": COLOR_RELEVANCE_MARGIN},
        {"component": "Deadline", "value": comp["deadline"]["value"],      "order": 4, "color": COLOR_RELEVANCE_DEADLINE},
        {"component": "Остаток",  "value": max(0.0, 1.0 - relevance),     "order": 5, "color": "rgba(255,255,255,0.04)"},
    ])
    bar = (
        alt.Chart(breakdown_df)
        .mark_bar(height=22)
        .encode(
            x=alt.X("value:Q", stack="zero", axis=None, scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(
                "component:N",
                scale=alt.Scale(
                    domain=["Match", "Stock", "Margin", "Deadline", "Остаток"],
                    range=[
                        COLOR_RELEVANCE_MATCH, COLOR_RELEVANCE_STOCK,
                        COLOR_RELEVANCE_MARGIN, COLOR_RELEVANCE_DEADLINE,
                        "rgba(255,255,255,0.04)",
                    ],
                ),
                legend=None,
            ),
            order="order:Q",
            tooltip=[
                alt.Tooltip("component:N", title="Компонент"),
                alt.Tooltip("value:Q", title="Вклад", format=".3f"),
            ],
        )
        .properties(height=22, width="container")
    )
    st.altair_chart(bar, use_container_width=True)

    # Legend — 4 columns
    legend_cols = st.columns(4)
    mq = comp["match_quality"]
    st_ = comp["stock"]
    mg = comp["margin"]
    dl = comp["deadline"]

    if in_stock_bm and stock_qty_bm > 0:
        st_caption = f"{stock_qty_bm}/50 × 25% = {st_['value']:.3f}"
    else:
        st_caption = "нет на складе"

    if price_max_bm is not None:
        mg_caption = f"{_format_nmc(float(price_max_bm))} → {mg['value']:.3f}"
    else:
        mg_caption = f"НМЦ не указана → {mg['value']:.3f}"

    if deadline_int is not None:
        dl_caption = f"{deadline_int} д → {dl['value']:.3f}"
    else:
        dl_caption = f"дедлайн не указан → {dl['value']:.3f}"

    legend_data = [
        ("Match quality", f"{mq['raw']:.2f} × 40% = {mq['value']:.3f}"),
        ("Склад",         st_caption),
        ("Маржа",         mg_caption),
        ("Дедлайн",       dl_caption),
    ]
    for col, (label, detail) in zip(legend_cols, legend_data):
        with col:
            st.markdown(f"**{label}**")
            st.caption(detail)

# ── Action panel helpers ─────────────────────────────────────────────────────

def _render_notification_preview(tender_row: pd.Series, catalog_row: pd.Series) -> None:
    """Превью уведомления: тендер + SKU."""
    st.markdown("**Предпросмотр уведомления**")
    tender_name = tender_row.get("name", tender_row.get("title", "—"))
    sku_name = catalog_row.get("name", catalog_row.get("description", "—"))
    sku_pn = catalog_row.get("part_number", "—")
    st.caption(f"Тендер: {tender_name}")
    st.caption(f"Позиция: {sku_pn} — {sku_name}")


def _render_settings_info() -> None:
    """Ссылка на настройки шаблонов."""
    st.caption(
        ":material/settings: Шаблоны уведомлений — [Настройки](/Настройки)",
    )


def _render_default_buttons(decision: str, form_key: str) -> None:
    """Кнопки по умолчанию: Участвовать / Пропустить / Запросить мнение."""
    btn_cols = st.columns([2, 2, 3])
    with btn_cols[0]:
        if st.button(
            ":material/check_circle: Участвовать",
            key=f"btn_participate_{form_key}",
            type="primary",
            use_container_width=True,
        ):
            st.session_state[form_key] = "participate"
            st.rerun()
    with btn_cols[1]:
        if st.button(
            ":material/cancel: Пропустить",
            key=f"btn_skip_{form_key}",
            use_container_width=True,
        ):
            st.session_state[form_key] = "skip"
            st.rerun()
    with btn_cols[2]:
        if st.button(
            ":material/help: Запросить мнение",
            key=f"btn_ask_{form_key}",
            use_container_width=True,
        ):
            st.session_state[form_key] = "ask"
            st.rerun()


def _render_participate_form(
    tender_row: pd.Series,
    catalog_row: pd.Series,
    notif_key: str,
    form_key: str,
) -> None:
    """Форма «Участвовать»."""
    _render_notification_preview(tender_row, catalog_row)
    comment = st.text_area(
        "Комментарий к заявке (необязательно)",
        placeholder="Например: есть в наличии 500 шт., готовы к отгрузке за 3 дня",
        key=f"ta_participate_{form_key}",
        height=80,
    )
    _render_settings_info()
    send_cols = st.columns([1, 1, 4])
    with send_cols[0]:
        if st.button(
            ":material/send: Отправить",
            key=f"send_participate_{form_key}",
            type="primary",
            use_container_width=True,
        ):
            st.session_state[notif_key] = {
                "type": "participate",
                "comment": comment,
                "ts": pd.Timestamp.now().strftime("%d.%m.%Y %H:%M"),
            }
            del st.session_state[form_key]
            st.toast("Уведомление об участии отправлено!", icon=":material/check_circle:")
            st.rerun()
    with send_cols[1]:
        if st.button(
            "Отмена",
            key=f"cancel_participate_{form_key}",
            use_container_width=True,
        ):
            del st.session_state[form_key]
            st.rerun()


def _render_skip_form(notif_key: str, form_key: str) -> None:
    """Форма «Пропустить»."""
    st.markdown("**Причина пропуска**")
    reason = st.pills(
        "Причина",
        options=["Нет в наличии", "Нерентабельно", "Не наша номенклатура", "Другое"],
        key=f"pills_skip_{form_key}",
        label_visibility="collapsed",
    )
    note = st.text_input(
        "Уточнение (необязательно)",
        placeholder="Дополнительные детали…",
        key=f"ti_skip_{form_key}",
    )
    send_cols = st.columns([1, 1, 4])
    with send_cols[0]:
        if st.button(
            ":material/send: Пропустить",
            key=f"send_skip_{form_key}",
            type="primary",
            use_container_width=True,
            disabled=reason is None,
        ):
            st.session_state[notif_key] = {
                "type": "skip",
                "reason": reason,
                "note": note,
                "ts": pd.Timestamp.now().strftime("%d.%m.%Y %H:%M"),
            }
            del st.session_state[form_key]
            st.toast("Тендер помечен как пропущенный.", icon=":material/cancel:")
            st.rerun()
    with send_cols[1]:
        if st.button(
            "Отмена",
            key=f"cancel_skip_{form_key}",
            use_container_width=True,
        ):
            del st.session_state[form_key]
            st.rerun()


def _render_ask_form(
    tender_row: pd.Series,
    catalog_row: pd.Series,
    best_match: dict,
    notif_key: str,
    form_key: str,
) -> None:
    """Форма «Запросить мнение»."""
    _render_notification_preview(tender_row, catalog_row)
    question = st.text_area(
        "Вопрос для команды",
        placeholder="Например: стоит ли участвовать при марже ниже 12%?",
        key=f"ta_ask_{form_key}",
        height=80,
    )
    send_cols = st.columns([1, 1, 4])
    with send_cols[0]:
        if st.button(
            ":material/send: Отправить",
            key=f"send_ask_{form_key}",
            type="primary",
            use_container_width=True,
            disabled=not question.strip() if question else True,
        ):
            st.session_state[notif_key] = {
                "type": "ask",
                "question": question,
                "ts": pd.Timestamp.now().strftime("%d.%m.%Y %H:%M"),
                "score": best_match.get("score", 0.0),
            }
            del st.session_state[form_key]
            st.toast("Запрос мнения отправлен!", icon=":material/help:")
            st.rerun()
    with send_cols[1]:
        if st.button(
            "Отмена",
            key=f"cancel_ask_{form_key}",
            use_container_width=True,
        ):
            del st.session_state[form_key]
            st.rerun()


def _render_sent_state(notif: dict, notif_key: str, form_key: str) -> None:
    """Состояние «отправлено» — показывает итог и доп. кнопки."""
    ntype = notif.get("type", "participate")
    ts = notif.get("ts", "—")

    if ntype == "participate":
        st.success(
            f":material/check_circle: Заявка на участие отправлена {ts}",
            icon=None,
        )
    elif ntype == "skip":
        reason = notif.get("reason", "—")
        st.warning(
            f":material/cancel: Пропущено {ts} — {reason}",
            icon=None,
        )
    else:
        st.info(
            f":material/help: Запрос мнения отправлен {ts}",
            icon=None,
        )

    extra_cols = st.columns([2, 2, 3])
    with extra_cols[0]:
        if st.button(
            ":material/undo: Отменить",
            key=f"undo_{notif_key}",
            use_container_width=True,
        ):
            del st.session_state[notif_key]
            st.rerun()
    with extra_cols[1]:
        if ntype != "ask":
            if st.button(
                ":material/help: Запросить мнение",
                key=f"extra_ask_{notif_key}",
                use_container_width=True,
            ):
                del st.session_state[notif_key]
                st.session_state[form_key] = "ask"
                st.rerun()


def _render_form(
    form_type: str,
    tender_row: pd.Series,
    catalog_row: pd.Series,
    best_match: dict,
    notif_key: str,
    form_key: str,
) -> None:
    """Диспетчер форм."""
    labels = {
        "participate": ":material/check_circle: Участвовать",
        "skip": ":material/cancel: Пропустить",
        "ask": ":material/help: Запросить мнение",
    }
    st.markdown(f"**{labels.get(form_type, form_type)}**")
    if form_type == "participate":
        _render_participate_form(tender_row, catalog_row, notif_key, form_key)
    elif form_type == "skip":
        _render_skip_form(notif_key, form_key)
    else:
        _render_ask_form(tender_row, catalog_row, best_match, notif_key, form_key)


# ── Блок 6: action panel ──────────────────────────────────────────────────────
notif_key = f"notif_{tender_id}"
form_key = f"form_{tender_id}"

with st.container(border=True):
    st.markdown("#### :primary[:material/send:] Действие")
    notif = st.session_state.get(notif_key)
    open_form = st.session_state.get(form_key)
    if notif is not None:
        _render_sent_state(notif, notif_key, form_key)
    elif open_form is not None:
        _render_form(open_form, tender_row, catalog_row, best_match, notif_key, form_key)
    else:
        _render_default_buttons(best_match.get("decision", "auto"), form_key)
