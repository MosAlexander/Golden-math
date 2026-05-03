from __future__ import annotations
import altair as alt
import pandas as pd
import streamlit as st
from dashboard.data_utils import (
    load_pipeline_results,
    load_tenders,
    load_catalog,
    get_summary_stats,
    get_run_metadata,
)
from dashboard.chart_utils import (
    DECISION_SCALE,
    DECISION_ORDER,
    RAINBOW_PALETTE,
)

st.markdown("## :primary[:material/dashboard:] Обзор")
st.caption("Сводка по последнему прогону пайплайна")

# ── Данные ──────────────────────────────────────────────────────────────────
tenders = load_tenders()
results = load_pipeline_results()
catalog = load_catalog()

# ── Блок KPI ────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/leaderboard:] KPI — Метрики")

    total_tenders = len(tenders)
    auto_count    = int((results["decision"] == "auto").sum())
    auto_pct      = round(auto_count / max(total_tenders, 1) * 100)
    urgent_count  = int((tenders["deadline_days"] <= 3).sum()) if "deadline_days" in tenders.columns else 0
    total_nmc     = tenders["price_max"].sum() if "price_max" in tenders.columns else 0
    total_nmc_str = f"{total_nmc / 1_000_000:.1f} М ₽" if total_nmc > 0 else "—"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Активных тендеров", total_tenders)
    col2.metric("Auto-match", auto_count, delta=f"{auto_pct}% от всех")
    col3.metric("Срочные", urgent_count)
    col3.caption("≤3 дней")
    col4.metric("Сумма НМЦ", total_nmc_str)

# ── Блок Аналитика ──────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/analytics:] Аналитика")

    cols = st.columns(3)

    # ── [1] Топ запрашиваемых SKU ────────────────────────────────────────────
    with cols[0]:
        st.markdown("**:primary[:material/inventory_2:] Топ запрашиваемых SKU**")

        df_for_options = results[results["decision"].isin(["auto", "borderline"])]
        valid_catalog_ids = set(df_for_options["catalog_id"])
        valid_categories = sorted(
            catalog[catalog["id"].isin(valid_catalog_ids)]["category"]
            .dropna()
            .unique()
            .tolist()
        )
        categories_options = ["Все"] + valid_categories

        selected_cat = st.selectbox(
            "Категория",
            options=categories_options,
            key="overview_sku_category",
            label_visibility="collapsed",
        )

        df_matches = results[results["decision"].isin(["auto", "borderline"])].copy()

        if selected_cat != "Все":
            cat_ids = set(catalog[catalog["category"] == selected_cat]["id"])
            df_matches = df_matches[df_matches["catalog_id"].isin(cat_ids)]

        if not df_matches.empty and "catalog_pn" in df_matches.columns:
            sku_counts = (
                df_matches.groupby("catalog_pn")
                .size()
                .reset_index(name="count")
                .nlargest(7, "count")
                .reset_index(drop=True)
            )
            sku_counts["color_idx"] = (sku_counts.index % len(RAINBOW_PALETTE)).astype(str)

            color_scale = alt.Scale(
                domain=[str(i) for i in range(len(RAINBOW_PALETTE))],
                range=RAINBOW_PALETTE,
            )

            chart = (
                alt.Chart(sku_counts)
                .mark_bar()
                .encode(
                    y=alt.Y("catalog_pn:N", sort="-x", title=None),
                    x=alt.X("count:Q", title="Кол-во матчей"),
                    color=alt.Color("color_idx:N", scale=color_scale, legend=None),
                    tooltip=["catalog_pn", "count"],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Нет данных для выбранной категории")

    # ── [2] НМЦ по категориям ────────────────────────────────────────────────
    with cols[1]:
        st.markdown("**:primary[:material/payments:] НМЦ по категориям**")

        zone_options = ["Все", "Auto", "Borderline", "Reject"]
        selected_zone = st.selectbox(
            "Зона",
            options=zone_options,
            key="overview_nmc_decision",
            label_visibility="collapsed",
        )

        results_with_cat = results.merge(
            catalog[["id", "category"]],
            left_on="catalog_id",
            right_on="id",
            how="left",
        )
        merged = tenders[["id", "price_max"]].merge(
            results_with_cat[["tender_id", "decision", "category"]],
            left_on="id",
            right_on="tender_id",
            how="inner",
        )

        if selected_zone != "Все":
            merged = merged[merged["decision"] == selected_zone.lower()]

        if not merged.empty:
            nmc_by_cat = (
                merged.groupby("category")["price_max"]
                .sum()
                .reset_index()
                .assign(nmc_mln=lambda df: df["price_max"] / 1_000_000)
                .nlargest(7, "nmc_mln")
                .reset_index(drop=True)
            )
            nmc_by_cat["color_idx"] = (nmc_by_cat.index % len(RAINBOW_PALETTE)).astype(str)

            color_scale2 = alt.Scale(
                domain=[str(i) for i in range(len(RAINBOW_PALETTE))],
                range=RAINBOW_PALETTE,
            )

            chart2 = (
                alt.Chart(nmc_by_cat)
                .mark_bar()
                .encode(
                    y=alt.Y("category:N", sort="-x", title=None),
                    x=alt.X("nmc_mln:Q", title="НМЦ, млн ₽"),
                    color=alt.Color("color_idx:N", scale=color_scale2, legend=None),
                    tooltip=[
                        alt.Tooltip("category:N", title="Категория"),
                        alt.Tooltip("nmc_mln:Q", title="НМЦ, млн ₽", format=".2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart2, use_container_width=True)
        else:
            st.info("Нет данных для выбранной зоны")

    # ── [3] Тендеры по регионам ──────────────────────────────────────────────
    with cols[2]:
        st.markdown("**:primary[:material/map:] Тендеры по регионам**")

        region_decision_options = ["Все", "Auto", "Borderline", "Reject"]
        selected_region_decision = st.selectbox(
            "Решение",
            options=region_decision_options,
            key="overview_region_decision",
            label_visibility="collapsed",
        )

        if selected_region_decision != "Все":
            matched_tenders = set(
                results[results["decision"] == selected_region_decision.lower()]["tender_id"]
            )
            tenders_filtered = tenders[tenders["id"].isin(matched_tenders)]
        else:
            tenders_filtered = tenders

        if not tenders_filtered.empty:
            nmc_by_region = (
                tenders_filtered.groupby("region")["price_max"]
                .sum()
                .reset_index()
                .assign(nmc_mln=lambda df: df["price_max"] / 1_000_000)
                .nlargest(7, "nmc_mln")
                .reset_index(drop=True)
            )
            nmc_by_region["color_idx"] = (nmc_by_region.index % len(RAINBOW_PALETTE)).astype(str)

            color_scale3 = alt.Scale(
                domain=[str(i) for i in range(len(RAINBOW_PALETTE))],
                range=RAINBOW_PALETTE,
            )

            chart3 = (
                alt.Chart(nmc_by_region)
                .mark_bar()
                .encode(
                    y=alt.Y("region:N", sort="-x", title=None),
                    x=alt.X("nmc_mln:Q", title="НМЦ, млн ₽"),
                    color=alt.Color("color_idx:N", scale=color_scale3, legend=None),
                    tooltip=[
                        alt.Tooltip("region:N", title="Регион"),
                        alt.Tooltip("nmc_mln:Q", title="НМЦ, млн ₽", format=".2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart3, use_container_width=True)
        else:
            st.info("Нет данных для выбранного решения")
