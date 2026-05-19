from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import logging

from dashboard.chart_utils import (
    PRIMARY_COLOR,
    PRIMARY_COLOR_FILL,
    COLOR_AUTO,
    COLOR_BORDERLINE,
    COLOR_REJECT,
    COLOR_RELEVANCE_MATCH,
    COLOR_RELEVANCE_STOCK,
    COLOR_RELEVANCE_MARGIN,
    COLOR_RELEVANCE_DEADLINE,
    DONUT_PALETTES,
)

logger = logging.getLogger(__name__)

from src.splink_config import (
    WEIGHT_PN_EXACT,
    WEIGHT_PN_PARTIAL,
    WEIGHT_MFR,
    WEIGHT_PN_MFR_BONUS,
    WEIGHT_CATEGORY,
    WEIGHT_VOLTAGE_EXACT,
    WEIGHT_VOLTAGE_CLOSE,
    WEIGHT_CURRENT_EXACT,
    WEIGHT_CURRENT_CLOSE,
    WEIGHT_DESCRIPTION,
)
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
        fillcolor=PRIMARY_COLOR_FILL,
        line=dict(color=PRIMARY_COLOR, width=1.5),
        marker=dict(size=8, color=PRIMARY_COLOR),
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
        height=300,
        showlegend=False,
        font=dict(family="Source Sans Pro, sans-serif"),
    )
    return fig


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
            v = WEIGHT_PN_EXACT
        elif t_pn in c_pn or c_pn in t_pn:
            v = WEIGHT_PN_PARTIAL
        else:
            v = 0.0
    else:
        v = 0.0
    cumulative += v
    contributions.append({"step": "PN", "value": v, "cumulative": cumulative})

    # 2. MFR (20%)
    t_mfr = (rec.manufacturer or "").lower()
    c_mfr = (cat.get("manufacturer") or "").lower()
    v = WEIGHT_MFR if t_mfr and c_mfr and t_mfr == c_mfr else 0.0
    cumulative += v
    contributions.append({"step": "MFR", "value": v, "cumulative": cumulative})

    # 3. PN+MFR bonus (5%) — архитектурный контракт из DECISIONS.md
    exact_pn = t_pn and c_pn and t_pn == c_pn
    exact_mfr = t_mfr and c_mfr and t_mfr == c_mfr
    v = WEIGHT_PN_MFR_BONUS if (exact_pn and exact_mfr) else 0.0
    cumulative += v
    contributions.append({"step": "Бонус", "value": v, "cumulative": cumulative})

    # 4. Категория (8%)
    v = WEIGHT_CATEGORY if rec.category and rec.category == cat.get("category", "") else 0.0
    cumulative += v
    contributions.append({"step": "Кат.", "value": v, "cumulative": cumulative})

    # 5. Напряжение (4%)
    t_v = rec.params.get("voltage_v")
    c_v = cat_params.get("voltage_v")
    if t_v and c_v:
        if t_v == c_v:
            v = WEIGHT_VOLTAGE_EXACT
        elif abs(t_v - c_v) / max(t_v, c_v, 1) < 0.1:
            v = WEIGHT_VOLTAGE_CLOSE
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
            v = WEIGHT_CURRENT_EXACT
        elif abs(t_a - c_a) / max(t_a, c_a, 1) < 0.15:
            v = WEIGHT_CURRENT_CLOSE
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
            v = WEIGHT_DESCRIPTION * overlap
        else:
            v = 0.0
    else:
        v = 0.0
    cumulative += v
    contributions.append({"step": "Описание", "value": v, "cumulative": cumulative})

    return contributions


# ── Donut chart ───────────────────────────────────────────────────────────────

def _build_donut_chart(contributions: list[dict], match: dict) -> go.Figure:
    """Donut с накоплением: показывает 7 факторов + сегмент «до 1.0».

    Заменяет waterfall. Использует те же contributions из _decompose_score.
    """
    decision = match.get("decision", "borderline")
    total = sum(c["value"] for c in contributions)
    gap_to_one = max(0.0, 1.0 - total)

    sorted_contribs = sorted(contributions, key=lambda c: c["value"], reverse=True)
    nonzero = [c for c in sorted_contribs if c["value"] > 0.001]

    labels = [c["step"] for c in nonzero] + ["до 1.0"]
    values = [c["value"] for c in nonzero] + [gap_to_one]

    base_palette = DONUT_PALETTES.get(decision, DONUT_PALETTES["borderline"])
    if len(nonzero) <= len(base_palette):
        colors = base_palette[: len(nonzero)] + ["rgba(255, 255, 255, 0.06)"]
    else:
        colors = (
            base_palette
            + [base_palette[-1]] * (len(nonzero) - len(base_palette))
            + ["rgba(255, 255, 255, 0.06)"]
        )

    center_color = {
        "auto": COLOR_AUTO,
        "borderline": COLOR_BORDERLINE,
        "reject": COLOR_REJECT,
    }.get(decision, COLOR_BORDERLINE)

    score = match.get("match_probability", 0.0)

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            sort=False,
            direction="clockwise",
            marker=dict(
                colors=colors,
                line=dict(color="#0E1117", width=2),
            ),
            textposition="outside",
            textinfo="label",
            textfont=dict(
                family="Source Sans Pro, sans-serif",
                size=11,
                color="rgba(250, 250, 250, 0.85)",
            ),
            hovertemplate="<b>%{label}</b><br>+%{value:.2f}<extra></extra>",
            showlegend=False,
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=30, l=40, r=40),
        height=300,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        annotations=[
            dict(
                text=f"<b>{int(score * 100)}%</b>",
                showarrow=False,
                font=dict(size=32, color=center_color, family="Source Sans Pro, sans-serif"),
                xref="paper", yref="paper",
                x=0.5, y=0.54,
            ),
            dict(
                text=decision,
                showarrow=False,
                font=dict(size=12, color="rgba(250, 250, 250, 0.6)", family="Source Sans Pro, sans-serif"),
                xref="paper", yref="paper",
                x=0.5, y=0.42,
            ),
        ],
    )

    return fig


# ── Match insights ────────────────────────────────────────────────────────────

@dataclass
class MatchInsights:
    what_matched: list[str]
    how_score_built: list[str]


def _get_match_insights(
    radar_axes: dict[str, float],
    contributions: list[dict],
    catalog_row: dict,
    best_match: dict,
) -> MatchInsights:
    """Собирает insights для объединённого блока «Анализ матча».

    Заменяет _get_radar_insights и _get_waterfall_insights.
    Каждая секция — до 3 пунктов.
    """
    decision = best_match.get("decision", "reject")
    prob = float(best_match.get("match_probability", 0))

    # Секция 1: атрибутные совпадения
    what: list[str] = []

    pn_v = contributions[0]["value"]
    if radar_axes.get("Part Number", 0) == 1.0:
        pn = catalog_row.get("part_number", "—")
        what.append(f"**PN exact match:** {pn}.")
    elif pn_v >= 0.40:
        what.append("**PN частичный:** описание совпадает с каталогом.")
    else:
        what.append("**Part number не извлечён:** самый сильный сигнал недоступен.")

    if radar_axes.get("Производитель", 0) == 1.0:
        mfr = catalog_row.get("manufacturer", "—")
        what.append(f"**MFR подтверждён:** {mfr}.")
    else:
        what.append("**MFR не указан:** тендер открытый по бренду.")

    matched_params = sum(
        1 for k in ("Напряжение", "Ток", "Категория")
        if radar_axes.get(k, 0) == 1.0
    )
    if matched_params >= 2:
        what.append(f"**Параметрика:** совпало {matched_params} из 3 характеристик.")
    elif matched_params == 1:
        what.append("**Параметрика:** слабый сигнал, 1 из 3 характеристик.")
    else:
        what.append("**Параметрика:** нет совпадений по V/A/категории.")

    # Секция 2: вклады в score
    how: list[str] = []

    pn_contrib = contributions[0]["value"]
    if pn_contrib >= 0.60:
        how.append(f"**PN +{pn_contrib:.2f}** — решающий фактор.")
    elif pn_contrib >= 0.40:
        how.append(f"**PN +{pn_contrib:.2f}** — частичное совпадение.")
    else:
        how.append("**PN +0.00** — Part number не найден.")

    mfr_contrib = contributions[1]["value"]
    if mfr_contrib > 0:
        how.append(f"**MFR +{mfr_contrib:.2f}** — производитель в ТЗ.")
    else:
        how.append("**MFR +0.00** — производитель не определён.")

    if decision == "auto":
        margin = prob - 0.92
        how.append(f"**Auto-зона** — порог пройден с запасом {margin * 100:.0f}%.")
    elif decision == "borderline":
        gap = 0.92 - prob
        how.append(f"**Не дотянули {gap * 100:.0f}%** до auto-зоны (≥0.92).")
    else:
        how.append("**Score ниже порога** — матч не подтверждён.")

    return MatchInsights(what_matched=what[:3], how_score_built=how[:3])


# ── Relevance decomposition ──────────────────────────────────────────────────

def _decompose_relevance(tender: dict, catalog: dict, match: dict) -> dict[str, float]:
    """Соответствует calculate_relevance из splink_config.py.

    ВАЖНО: при изменении формулы в src/splink_config.py::calculate_relevance
    нужно синхронно обновить:
      1. Эту функцию
      2. Caption-форматы в легенде блока 4 в этом же файле (формулы '× 40%' и т.д.)
    Иначе цифры в дашборде разойдутся с реальным relevance.
    """
    # Match quality
    mq = match["match_probability"] * 0.40

    # Stock
    in_stock = catalog.get("in_stock", False)
    qty = catalog.get("stock_qty", 0)
    if in_stock and qty > 0:
        sa = min(qty / 50, 1.0) * 0.25
    else:
        sa = 0.0

    # Margin
    price = tender.get("price_max", 0) or 0
    if price > 100_000:
        me = 0.20
    elif price > 50_000:
        me = 0.12
    else:
        me = 0.05

    # Deadline
    days = tender.get("deadline_days", 30) or 30
    if days <= 5:
        du = 0.15
    elif days <= 10:
        du = 0.10
    elif days <= 20:
        du = 0.05
    else:
        du = 0.02

    return {
        "match_quality": mq,
        "stock": sa,
        "margin": me,
        "deadline": du,
    }


# ── Блок 1: match card ───────────────────────────────────────────────────────

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

# Предвычисляем данные для блока 2
prob_pct      = int(float(best_match.get("match_probability", 0)) * 100)
radar_axes    = _compute_radar_axes(tender_id, tender_row.get("name", ""), best_match["catalog_id"])
contributions = _decompose_score(tender_id, tender_row.get("name", ""), best_match["catalog_id"])

# ── Блок 1: карточка матча ────────────────────────────────────────────────────
_render_match_card(tender_row, catalog_row, best_match)

# ── Блок 2: Анализ матча (радар + donut + insights) ───────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/analytics:] Анализ матча")
    radar_col, donut_col, insights_col = st.columns([1.2, 1.2, 1])

    with radar_col:
        st.markdown("**Что совпало в товаре**")
        radar_fig = _build_radar_chart(radar_axes)
        st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})

    with donut_col:
        st.markdown(f"**Из чего сложилась уверенность {prob_pct}%**")
        donut_fig = _build_donut_chart(contributions, best_match)
        st.plotly_chart(donut_fig, use_container_width=True, config={"displayModeBar": False})

    with insights_col:
        insights = _get_match_insights(radar_axes, contributions, catalog_row, best_match)

        st.markdown(":primary[:material/lightbulb:] **KEY INSIGHTS**")

        st.markdown(":primary[**Что совпало в товаре**]")
        for line in insights.what_matched:
            st.markdown(line)

        st.markdown(":primary[**Из чего сложилась уверенность**]")
        for line in insights.how_score_built:
            st.markdown(line)

# ── Блок 3: LLM-плейсхолдер (только borderline) ──────────────────────────────
if best_match.get("decision") == "borderline":
    with st.container(border=True):
        st.markdown("#### :primary[:material/auto_awesome:] Заключение AI-эксперта")
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

# ── Блок 4: relevance breakdown ───────────────────────────────────────────────
relevance = float(best_match.get("relevance", 0))
comp = _decompose_relevance(tender_row, catalog_row, best_match)

with st.container(border=True):
    title_col, value_col = st.columns([3, 1])
    with title_col:
        st.markdown("#### :primary[:material/leaderboard:] Стоит ли брать в работу")
    with value_col:
        st.markdown(f"### :primary[**{relevance:.2f}**]")
        st.caption("Relevance")

    # Segmented bar
    breakdown_df = pd.DataFrame([
        {"component": "Match",    "value": comp["match_quality"], "order": 1, "color": COLOR_RELEVANCE_MATCH},
        {"component": "Stock",    "value": comp["stock"],         "order": 2, "color": COLOR_RELEVANCE_STOCK},
        {"component": "Margin",   "value": comp["margin"],        "order": 3, "color": COLOR_RELEVANCE_MARGIN},
        {"component": "Deadline", "value": comp["deadline"],      "order": 4, "color": COLOR_RELEVANCE_DEADLINE},
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
    legend_data = [
        ("Качество матча", f"{best_match['match_probability']:.2f} × 40% = {comp['match_quality']:.3f}"),
        ("Склад",          f"{int(catalog_row.get('stock_qty', 0))} шт × 25% = {comp['stock']:.3f}"),
        ("Маржа НМЦ",      f"{_format_nmc(tender_row.get('price_max'))} × 20% = {comp['margin']:.3f}"),
        ("Срочность",      f"{int(tender_row.get('deadline_days', 0))} дней × 15% = {comp['deadline']:.3f}"),
    ]
    for col, (label, detail) in zip(legend_cols, legend_data):
        with col:
            st.markdown(f"**{label}**")
            st.caption(detail)

# ── Action panel helpers ─────────────────────────────────────────────────────

def _render_notification_preview(tender_row: dict, catalog_row: dict) -> None:
    """Превью уведомления: тендер + SKU."""
    st.markdown("**Предпросмотр уведомления**")
    tender_name = tender_row.get("name", tender_row.get("title", "—"))
    sku_name = catalog_row.get("name", catalog_row.get("description", "—"))
    sku_pn = catalog_row.get("part_number", "—")
    st.caption(f"Тендер: {tender_name}")
    st.caption(f"Позиция: {sku_pn} — {sku_name}")



def _render_default_buttons(decision: str, form_key: str) -> None:
    """Кнопки по умолчанию: Участвовать / Пропустить / Запросить мнение."""
    btn_cols = st.columns(3)
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
    tender_row: dict,
    catalog_row: dict,
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
    tender_row: dict,
    catalog_row: dict,
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
    tender_row: dict,
    catalog_row: dict,
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


# ── Блок 5: action panel ──────────────────────────────────────────────────────
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
