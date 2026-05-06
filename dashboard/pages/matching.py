from __future__ import annotations

from datetime import datetime

import streamlit as st

from dashboard.chart_utils import (
    COLOR_AUTO,
    COLOR_BORDERLINE,
    COLOR_REJECT,
)
from dashboard.data_utils import (
    get_run_metadata,
    load_catalog,
    load_pipeline_results,
    load_tenders,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

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


# ── Block 1: match card ───────────────────────────────────────────────────────

def _render_match_card(tender_row: dict, catalog_row: dict, best_match: dict) -> None:
    with st.container(border=True):
        st.markdown("#### :primary[:material/article:] Карточка матча")

        col1, col2, col3, col4 = st.columns(4)

        # 1. Тендер
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

        # 2. Лучший SKU
        with col2:
            st.caption("Лучший SKU")
            st.markdown(f"**{catalog_row.get('id', '—')}**")
            in_stock = catalog_row.get("in_stock", False)
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

        # 3. Match probability
        with col3:
            st.caption("Match probability")
            prob = float(best_match.get("match_probability", 0))
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

        # 4. Relevance
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

# Загрузка данных
results  = load_pipeline_results()
tenders  = load_tenders()
catalog  = load_catalog()
metadata = get_run_metadata()

tender_matches = results[results["tender_id"] == tender_id]
if tender_matches.empty:
    st.markdown("## :primary[:material/insights:] Матчинг")
    st.warning("Для этого тендера не найдено совпадений с каталогом.")
    st.stop()

best_match  = tender_matches.loc[tender_matches["relevance"].idxmax()].to_dict()

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

# ── Блок 1: карточка матча ────────────────────────────────────────────────────
_render_match_card(tender_row, catalog_row, best_match)

# ── Блок 2: радар (раунд 2) ───────────────────────────────────────────────────
with st.container(border=True):
    st.info(
        "Блок «Что совпало в товаре» (радар) — следующие раунды",
        icon=":material/track_changes:",
    )

# ── Блок 3: waterfall (раунд 2) ───────────────────────────────────────────────
with st.container(border=True):
    st.info(
        "Блок «Из чего сложилась уверенность» (waterfall) — следующие раунды",
        icon=":material/stairs:",
    )

# ── Блок 4: LLM (раунд 3) ────────────────────────────────────────────────────
with st.container(border=True):
    st.info(
        "Блок LLM-эксперта (только borderline) — следующие раунды",
        icon=":material/auto_awesome:",
    )

# ── Блок 5: relevance breakdown (раунд 3) ────────────────────────────────────
with st.container(border=True):
    st.info(
        "Блок «Стоит ли брать в работу» (relevance breakdown) — следующие раунды",
        icon=":material/leaderboard:",
    )

# ── Блок 6: action panel (раунд 4) ───────────────────────────────────────────
with st.container(border=True):
    st.info(
        "Блок действий (участвовать / пропустить / запросить мнение) — следующие раунды",
        icon=":material/send:",
    )
