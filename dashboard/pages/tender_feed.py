from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.data_utils import (
    load_catalog,
    load_pipeline_results,
    load_tenders,
)


def _format_nmc(v: float | None) -> str:
    if not v or v == 0:
        return "—"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f} М ₽"
    if v >= 1_000:
        return f"{v / 1_000:.0f} К ₽"
    return f"{v:.0f} ₽"


@st.cache_data
def _compute_scenarios(tender_ids: tuple, names: tuple) -> dict:
    from src.normalizer_electronics import normalize_tender_item
    return {
        tid: normalize_tender_item(tid, name).match_scenario
        for tid, name in zip(tender_ids, names)
    }


@st.cache_data
def _build_base_df() -> pd.DataFrame:
    results = load_pipeline_results()
    tenders = load_tenders()
    catalog = load_catalog()

    active = results[results["decision"].isin(["auto", "borderline"])].copy()

    # один тендер = одна строка (лучший по relevance)
    idx = active.groupby("tender_id")["relevance"].idxmax()
    active = active.loc[idx].reset_index(drop=True)

    # сценарии
    scenarios = _compute_scenarios(
        tuple(tenders["id"]),
        tuple(tenders["name"]),
    )
    active["match_scenario"] = active["tender_id"].map(scenarios)

    # название тендера из tenders (оригинальное)
    tender_names = tenders.set_index("id")["name"]
    active["tender_name_orig"] = active["tender_id"].map(tender_names)

    # категория из каталога
    cat_index = catalog.set_index("id")
    active["category"] = active["catalog_id"].map(cat_index["category"])

    return active


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    search = st.session_state.get("feed_search", "").strip().lower()
    category = st.session_state.get("feed_category", "Все")
    scenario = st.session_state.get("feed_scenario", "Все")
    nmc = st.session_state.get("feed_nmc", "Все")
    deadline = st.session_state.get("feed_deadline", "Все")

    if search:
        mask = df["tender_name_orig"].str.lower().str.contains(search, na=False)
        df = df[mask]

    if category != "Все":
        df = df[df["category"] == category]

    if scenario != "Все":
        df = df[df["match_scenario"] == scenario]

    if nmc != "Все":
        p = df["price_max"]
        ranges = {
            "до 100К":   p < 100_000,
            "100К–500К": (p >= 100_000) & (p < 500_000),
            "500К–2М":   (p >= 500_000) & (p < 2_000_000),
            "2М–10М":    (p >= 2_000_000) & (p < 10_000_000),
            ">10М":      p >= 10_000_000,
        }
        df = df[ranges[nmc]]

    if deadline != "Все":
        d = df["deadline_days"]
        thresholds = {"≤3 дней": 3, "≤7 дней": 7, "≤14 дней": 14}
        df = df[d <= thresholds[deadline]]

    return df


def _to_display(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.iterrows():
        stock = f"{int(r['stock_qty'])} шт" if r["in_stock"] and r["stock_qty"] > 0 else "—"
        rows.append({
            "ID":               r["tender_id"],
            "Название":         r["tender_name_orig"],
            "SKU из каталога":  r["catalog_pn"],
            "Сценарий":         r.get("match_scenario", "—"),
            "Match prob":       round(float(r["match_probability"]), 4),
            "НМЦ":              _format_nmc(r["price_max"]),
            "Дедлайн":          f"{int(r['deadline_days'])} д",
            "Склад":            stock,
            "Relevance":        round(float(r["relevance"]), 4),
        })
    return pd.DataFrame(rows)


# ── Заголовок страницы ─────────────────────────────────────────────────────────
st.markdown("## :primary[:material/list_alt:] Лента тендеров")
st.caption("Активные тендеры с матчами, сортировка по relevance")

# ── Блок фильтров ──────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/filter_list:] Фильтры")

    st.text_input(
        "Поиск",
        placeholder="Артикул, название...",
        key="feed_search",
        label_visibility="visible",
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        catalog = load_catalog()
        results = load_pipeline_results()
        active_cat_ids = results[results["decision"].isin(["auto", "borderline"])]["catalog_id"].unique()
        active_cats = sorted(
            catalog[catalog["id"].isin(active_cat_ids)]["category"].dropna().unique().tolist()
        )
        st.selectbox(
            "Категория",
            options=["Все"] + active_cats,
            key="feed_category",
            label_visibility="visible",
        )

    with col2:
        st.selectbox(
            "Сценарий",
            options=["Все", "A", "B", "C"],
            key="feed_scenario",
            label_visibility="visible",
        )

    with col3:
        st.selectbox(
            "НМЦ",
            options=["Все", "до 100К", "100К–500К", "500К–2М", "2М–10М", ">10М"],
            key="feed_nmc",
            label_visibility="visible",
        )

    with col4:
        st.selectbox(
            "Дедлайн",
            options=["Все", "≤3 дней", "≤7 дней", "≤14 дней"],
            key="feed_deadline",
            label_visibility="visible",
        )

    with col5:
        st.selectbox(
            "Источник",
            options=["—"],
            key="feed_source",
            disabled=True,
            label_visibility="visible",
            help="Доступно после интеграции TenderGuru (Gate 8)",
        )

# ── Блок таблицы ───────────────────────────────────────────────────────────────
base_df = _build_base_df()
filtered = _apply_filters(base_df)
filtered = filtered.sort_values("relevance", ascending=False)
display_df = _to_display(filtered)

with st.container(border=True):
    st.markdown(f"#### :primary[:material/table_view:] Активные тендеры ({len(display_df)})")

    # блок "Текущий выбор" над таблицей
    if "selected_tender_id" in st.session_state:
        sel_id = st.session_state["selected_tender_id"]
        info_col, btn_col = st.columns([6, 1])
        with info_col:
            st.info(f"Текущий выбор: {sel_id}", icon=":material/info:")
        with btn_col:
            st.write("")  # выравнивание по вертикали
            if st.button("Сбросить", key="feed_clear_selection"):
                del st.session_state["selected_tender_id"]
                st.rerun()

    column_config = {
        "ID": st.column_config.TextColumn("ID", width="small"),
        "Название": st.column_config.TextColumn(
            "Название",
            width="medium",
            help="Полное название тендера",
        ),
        "SKU из каталога": st.column_config.TextColumn("SKU из каталога", width="small"),
        "Сценарий": st.column_config.TextColumn("Сценарий", width="small"),
        "Match prob": st.column_config.ProgressColumn(
            "Match prob",
            min_value=0,
            max_value=1,
            format="percent",
        ),
        "НМЦ": st.column_config.TextColumn("НМЦ", width="small"),
        "Дедлайн": st.column_config.TextColumn("Дедлайн", width="small"),
        "Склад": st.column_config.TextColumn("Склад", width="small"),
        "Relevance": st.column_config.ProgressColumn(
            "Relevance",
            min_value=0,
            max_value=1,
            format="percent",
        ),
    }

    event = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        selection_mode="single-row",
        on_select="rerun",
    )

    if event.selection.rows:
        selected_idx = event.selection.rows[0]
        tender_id = display_df.iloc[selected_idx]["ID"]
        st.session_state["selected_tender_id"] = tender_id
        st.toast(f"Выбран тендер {tender_id}", icon=":material/done:")
