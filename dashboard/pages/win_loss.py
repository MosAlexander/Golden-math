"""win_loss.py — Разбор тендеров: что GoldenMatch рассчитал по каждому тендеру."""
from __future__ import annotations

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.chart_utils import (
    COLOR_AUTO,
    COLOR_BAR_COUNT,
    COLOR_BAR_MONEY,
    COLOR_BORDERLINE,
    COLOR_CHART_TEXT,
    COLOR_NEUTRAL,
    COLOR_REJECT,
    NMC_SANKEY_GRADIENT,
)
from dashboard.data_utils import load_catalog, load_pipeline_results, load_tenders

# ── Константы ──────────────────────────────────────────────────────────────────

_DEC_LABEL = {
    "auto":       "Auto ≥0.92",
    "borderline": "Borderline 0.75–0.92",
    "reject":     "Reject <0.75",
    "no_match":   "Нет матча",
}
_DEC_COLOR = {
    "auto":       COLOR_AUTO,
    "borderline": COLOR_BORDERLINE,
    "reject":     COLOR_REJECT,
    "no_match":   COLOR_NEUTRAL,
}


# ── Хелперы ────────────────────────────────────────────────────────────────────
def _nmc_bucket(price) -> str:
    if price is None or pd.isna(price):
        return "< 100К₽"
    price = float(price)
    if price > 2_000_000:
        return "2–30М₽"
    if price > 500_000:
        return "500К–2М₽"
    if price > 100_000:
        return "100–500К₽"
    return "< 100К₽"


def _build_full_table(
    tenders_df: pd.DataFrame,
    results_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
) -> pd.DataFrame:
    best = (
        results_df.sort_values("match_probability", ascending=False)
        .groupby("tender_id")
        .first()
        .reset_index()
    )
    # price_max берём из tenders (левая сторона) — без дублей.
    cols = [
        "tender_id", "catalog_id", "catalog_pn",
        "match_probability", "decision",
    ]
    best_cols = [c for c in cols if c in best.columns]
    merged = tenders_df.rename(columns={"id": "tender_id"}).merge(
        best[best_cols], on="tender_id", how="left"
    )
    merged["decision"] = merged["decision"].fillna("no_match")
    merged["match_probability"] = merged["match_probability"].fillna(0.0)

    cat_map = catalog_df.set_index("id")["category"].to_dict() if "category" in catalog_df.columns else {}
    merged["category"] = merged["catalog_id"].map(cat_map).fillna("Нет совпадения")

    return merged


def _calc_y_positions(sizes: list[float], pad_frac: float = 0.05) -> list[float]:
    """y-центры узлов Sankey сверху вниз с учётом пропорциональных размеров."""
    total = sum(sizes)
    if total == 0:
        return [0.5] * len(sizes)
    n_gaps = max(len(sizes) - 1, 1)
    available = 1.0 - pad_frac * n_gaps
    centers, cursor = [], 0.0
    for s in sizes:
        h = s / total * available
        cursor += h / 2
        centers.append(min(max(cursor, 0.01), 0.99))
        cursor += h / 2 + pad_frac
    return centers




# ── Загрузка данных ─────────────────────────────────────────────────────────────
results_df = load_pipeline_results()
tenders_df = load_tenders()
catalog_df = load_catalog()
df = _build_full_table(tenders_df, results_df, catalog_df)

# ── Заголовок ──────────────────────────────────────────────────────────────────
st.markdown("## :primary[:material/analytics:] Разбор тендеров")
st.caption("GoldenMatch оценил каждый тендер — сценарий, PN, решение и вероятность совпадения")
st.info(
    ":material/info: Seed-данные: 14 тендеров × 15 SKU Radal. "
    "При подключении TenderGuru данные обновляются ежедневно."
)

# ── KPI ────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Обработано", len(df))
    with c2:
        st.metric("Авто-матч", int((df["decision"] == "auto").sum()))
    with c3:
        st.metric("Пограничная зона", int((df["decision"] == "borderline").sum()))
    with c4:
        st.metric(
            "Нет совпадения",
            int(df["decision"].isin(["reject", "no_match"]).sum()),
        )

# ── БЛОК A: Воронка решений по НМЦ — Sankey ───────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/alt_route:] Воронка решений по НМЦ")
    st.caption("Куда уходят тендеры: решения GoldenMatch → размер НМЦ")

    if df.empty:
        st.info("Нет данных pipeline — запустите python -m src.demo_pipeline.")
        st.stop()

    df_s = df.copy()
    df_s["nmc"] = df_s["price_max"].apply(_nmc_bucket)

    dec_order = ["auto", "borderline", "reject", "no_match"]
    nmc_order_visual = ["2–30М₽", "500К–2М₽", "100–500К₽", "< 100К₽"]

    node_labels = [_DEC_LABEL[d] for d in dec_order] + nmc_order_visual
    node_colors = [_DEC_COLOR[d] for d in dec_order] + NMC_SANKEY_GRADIENT

    dec_to_idx = {d: i for i, d in enumerate(dec_order)}
    nmc_to_idx = {nmc: 4 + i for i, nmc in enumerate(nmc_order_visual)}

    left_sizes  = [max(int((df_s["decision"] == d).sum()), 1) for d in dec_order]
    right_sizes = [max(int((df_s["nmc"] == nmc).sum()), 1) for nmc in nmc_order_visual]
    node_x = [0.01] * 4 + [0.99] * 4
    node_y = _calc_y_positions(left_sizes, pad_frac=0.07) + _calc_y_positions(right_sizes, pad_frac=0.07)

    grouped = df_s.groupby(["decision", "nmc"]).size().reset_index(name="count")

    link_src, link_tgt, link_val, link_col = [], [], [], []
    for _, lrow in grouped.iterrows():
        dec = lrow["decision"]
        nmc = lrow["nmc"]
        if dec not in dec_to_idx or nmc not in nmc_to_idx:
            continue
        link_src.append(dec_to_idx[dec])
        link_tgt.append(nmc_to_idx[nmc])
        link_val.append(int(lrow["count"]))
        base = _DEC_COLOR[dec].lstrip("#")
        r, g, b = int(base[0:2], 16), int(base[2:4], 16), int(base[4:6], 16)
        link_col.append(f"rgba({r},{g},{b},0.45)")

    fig_sankey = go.Figure(
        go.Sankey(
            arrangement="fixed",
            node=dict(
                pad=20,
                thickness=20,
                line=dict(color="rgba(255,255,255,0.1)", width=0.5),
                label=node_labels,
                color=node_colors,
                x=node_x,
                y=node_y,
            ),
            link=dict(
                source=link_src,
                target=link_tgt,
                value=link_val,
                color=link_col,
            ),
        )
    )
    fig_sankey.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_CHART_TEXT, size=12),
        margin=dict(l=10, r=10, t=20, b=10),
        height=420,
    )

    col_a_chart, col_a_ins = st.columns([3, 1])
    with col_a_chart:
        st.plotly_chart(fig_sankey, use_container_width=True)
    with col_a_ins:
        st.markdown(":primary[:material/lightbulb:] **Key Insights**")

        # 1 строка на тендер — берём решение с макс. match_probability.
        df_per_tender = df

        auto_cnt   = int((df_per_tender["decision"] == "auto").sum())
        border_cnt = int((df_per_tender["decision"] == "borderline").sum())
        nm_cnt     = int((df_per_tender["decision"] == "no_match").sum())
        total_cnt  = len(df_per_tender)

        auto_sum_m = float(
            df_per_tender.loc[df_per_tender["decision"] == "auto", "price_max"]
                         .fillna(0).sum()
        ) / 1_000_000
        border_sum_m = float(
            df_per_tender.loc[df_per_tender["decision"] == "borderline", "price_max"]
                         .fillna(0).sum()
        ) / 1_000_000

        covered_cnt  = auto_cnt + border_cnt
        coverage_pct = (covered_cnt / total_cnt * 100) if total_cnt > 0 else 0.0

        st.markdown(f"{auto_cnt} авто-матчей на {auto_sum_m:.1f} млн ₽ — высокая точность совпадения по каталогу")
        st.markdown(f"{border_cnt} пограничных на {border_sum_m:.1f} млн ₽ — нужна проверка LLM")
        if nm_cnt > 0:
            st.markdown(f"{nm_cnt} тендеров без матча — ждут Splink (Gate 8)")
        st.markdown(f"Покрытие сегодня: {coverage_pct:.0f}% ({covered_cnt}/{total_cnt} тендеров)")

# ── БЛОК B: Категории спроса (два бара рядом) ──────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/category:] Категории спроса")
    st.caption("Где сосредоточены деньги и где идут потоки")

    # 1 тендер = 1 строка; «Нет совпадения» не является категорией компонента
    df_cat = df.copy()
    df_cat = df_cat[
        df_cat["category"].notna()
        & (df_cat["category"] != "")
        & (df_cat["category"] != "Нет совпадения")
    ]

    if df_cat.empty:
        st.info("Нет данных по категориям компонентов.")
    else:
        agg = (
            df_cat.groupby("category")
                  .agg(
                      n=("tender_id", "count"),
                      sum_nmc=("price_max", "sum"),
                  )
                  .reset_index()
        )
        agg["sum_nmc_m"] = agg["sum_nmc"] / 1_000_000
        agg = agg.sort_values("sum_nmc_m", ascending=False).reset_index(drop=True)

        TOP_N = 7
        if len(agg) > TOP_N:
            top = agg.head(TOP_N)
            tail = agg.iloc[TOP_N:]
            other_row = pd.DataFrame([{
                "category": "Прочее",
                "n": int(tail["n"].sum()),
                "sum_nmc": float(tail["sum_nmc"].sum()),
                "sum_nmc_m": float(tail["sum_nmc_m"].sum()),
            }])
            agg = pd.concat([top, other_row], ignore_index=True)

        sort_order = agg["category"].tolist()
        chart_height = max(280, len(sort_order) * 38)

        col_cat_chart, col_cat_ins = st.columns([3, 1])

        with col_cat_chart:
            sub_count, sub_money = st.columns(2)

            with sub_count:
                st.caption("По числу тендеров")
                chart_count = (
                    alt.Chart(agg)
                    .mark_bar(cornerRadiusEnd=3, color=COLOR_BAR_COUNT)
                    .encode(
                        y=alt.Y(
                            "category:N",
                            sort=sort_order,
                            title=None,
                            axis=alt.Axis(labelLimit=140, labelFontSize=12),
                        ),
                        x=alt.X(
                            "n:Q",
                            title="Тендеров",
                            axis=alt.Axis(tickMinStep=1, labelFontSize=11),
                        ),
                        tooltip=[
                            alt.Tooltip("category:N", title="Категория"),
                            alt.Tooltip("n:Q", title="Тендеров"),
                        ],
                    )
                    .properties(height=chart_height)
                )
                st.altair_chart(chart_count, use_container_width=True)

            with sub_money:
                st.caption("По сумме НМЦ, млн ₽")
                chart_money = (
                    alt.Chart(agg)
                    .mark_bar(cornerRadiusEnd=3, color=COLOR_BAR_MONEY)
                    .encode(
                        y=alt.Y(
                            "category:N",
                            sort=sort_order,
                            title=None,
                            axis=alt.Axis(labels=False, ticks=False),
                        ),
                        x=alt.X(
                            "sum_nmc_m:Q",
                            title="млн ₽",
                            axis=alt.Axis(labelFontSize=11),
                        ),
                        tooltip=[
                            alt.Tooltip("category:N", title="Категория"),
                            alt.Tooltip("sum_nmc_m:Q", title="Сумма, млн ₽", format=".2f"),
                        ],
                    )
                    .properties(height=chart_height)
                )
                st.altair_chart(chart_money, use_container_width=True)

        with col_cat_ins:
            st.markdown(":primary[:material/lightbulb:] **Key Insights**")

            total_n = int(agg["n"].sum())
            total_m = float(agg["sum_nmc_m"].sum())
            top_row = agg.iloc[0]
            top_cat = top_row["category"]
            top_n = int(top_row["n"])
            top_m = float(top_row["sum_nmc_m"])
            top_money_share = (top_m / total_m * 100) if total_m > 0 else 0.0
            top_count_share = (top_n / total_n * 100) if total_n > 0 else 0.0

            # Пара категорий с равным числом тендеров, но разными деньгами
            same_n_pairs = []
            for i in range(len(agg)):
                for j in range(i + 1, len(agg)):
                    a, b = agg.iloc[i], agg.iloc[j]
                    if int(a["n"]) == int(b["n"]) and int(a["n"]) >= 2:
                        ratio = (
                            float(a["sum_nmc_m"]) / float(b["sum_nmc_m"])
                            if b["sum_nmc_m"] > 0 else 0
                        )
                        if ratio >= 3:
                            same_n_pairs.append((a, b, ratio))
            if same_n_pairs:
                a, b, ratio = same_n_pairs[0]
                st.markdown(
                    f"{a['category']} и {b['category']} — по {int(a['n'])} тендеров, "
                    f"но в деньгах разрыв ×{ratio:.0f} "
                    f"({a['sum_nmc_m']:.1f} vs {b['sum_nmc_m']:.1f} млн ₽)"
                )

            st.markdown(
                f"{top_cat} — {top_money_share:.0f}% всех денег при "
                f"{top_count_share:.0f}% тендеров: главный денежный спрос"
            )

            tail_cats = agg[agg["n"] == 1]
            if len(tail_cats) >= 2:
                max_tail_m = float(tail_cats["sum_nmc_m"].max())
                tail_names = ", ".join(tail_cats["category"].tolist())
                st.markdown(
                    f"{tail_names} — по 1 тендеру до {max_tail_m:.2f} млн ₽: "
                    f"длинный хвост мелких"
                )

            if len(agg) >= 2 and total_m > 0:
                top2_money_share = float(agg.head(2)["sum_nmc_m"].sum()) / total_m * 100
                top2_count_share = int(agg.head(2)["n"].sum()) / total_n * 100
                if top2_money_share >= 80:
                    st.markdown(
                        f"Топ-2 категории = {top2_money_share:.0f}% денег и "
                        f"{top2_count_share:.0f}% тендеров — узкий профиль"
                    )

# ── БЛОК C: Топ SKU по тендерам (два бара рядом) ───────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/inventory_2:] Топ SKU по тендерам")
    st.caption("Какие позиции каталога чаще всего попадают в матч и сколько денег приносят")

    # 1 тендер = 1 строка; берём лучший матч; отбрасываем «нет совпадения»
    df_sku = df.copy()
    df_sku = df_sku[
        df_sku["catalog_pn"].notna()
        & (df_sku["catalog_pn"] != "")
        & (df_sku["catalog_pn"] != "—")
        & df_sku["decision"].isin(["auto", "borderline"])
    ]

    if df_sku.empty:
        st.info("Нет SKU с подтверждённым матчем.")
    else:
        agg_sku = (
            df_sku.groupby("catalog_pn")
                  .agg(
                      n=("tender_id", "count"),
                      sum_nmc=("price_max", "sum"),
                  )
                  .reset_index()
        )
        agg_sku["sum_nmc_m"] = agg_sku["sum_nmc"] / 1_000_000
        agg_sku = agg_sku.sort_values("sum_nmc_m", ascending=False).reset_index(drop=True)

        TOP_N = 15
        if len(agg_sku) > TOP_N:
            top = agg_sku.head(TOP_N)
            tail = agg_sku.iloc[TOP_N:]
            other_row = pd.DataFrame([{
                "catalog_pn": "Прочее",
                "n": int(tail["n"].sum()),
                "sum_nmc": float(tail["sum_nmc"].sum()),
                "sum_nmc_m": float(tail["sum_nmc_m"].sum()),
            }])
            agg_sku = pd.concat([top, other_row], ignore_index=True)

        sort_order = agg_sku["catalog_pn"].tolist()
        chart_height = max(280, len(sort_order) * 28)

        col_sku_chart, col_sku_ins = st.columns([3, 1])

        with col_sku_chart:
            sub_count, sub_money = st.columns(2)

            with sub_count:
                st.caption("По числу тендеров")
                chart_count = (
                    alt.Chart(agg_sku)
                    .mark_bar(cornerRadiusEnd=3, color=COLOR_BAR_COUNT)
                    .encode(
                        y=alt.Y(
                            "catalog_pn:N",
                            sort=sort_order,
                            title=None,
                            axis=alt.Axis(labelLimit=180, labelFontSize=11),
                        ),
                        x=alt.X(
                            "n:Q",
                            title="Тендеров",
                            axis=alt.Axis(tickMinStep=1, labelFontSize=11),
                        ),
                        tooltip=[
                            alt.Tooltip("catalog_pn:N", title="SKU"),
                            alt.Tooltip("n:Q", title="Тендеров"),
                        ],
                    )
                    .properties(height=chart_height)
                )
                st.altair_chart(chart_count, use_container_width=True)

            with sub_money:
                st.caption("По сумме НМЦ, млн ₽")
                chart_money = (
                    alt.Chart(agg_sku)
                    .mark_bar(cornerRadiusEnd=3, color=COLOR_BAR_MONEY)
                    .encode(
                        y=alt.Y(
                            "catalog_pn:N",
                            sort=sort_order,
                            title=None,
                            axis=alt.Axis(labels=False, ticks=False),
                        ),
                        x=alt.X(
                            "sum_nmc_m:Q",
                            title="млн ₽",
                            axis=alt.Axis(labelFontSize=11),
                        ),
                        tooltip=[
                            alt.Tooltip("catalog_pn:N", title="SKU"),
                            alt.Tooltip("sum_nmc_m:Q", title="Сумма, млн ₽", format=".2f"),
                        ],
                    )
                    .properties(height=chart_height)
                )
                st.altair_chart(chart_money, use_container_width=True)

        with col_sku_ins:
            st.markdown(":primary[:material/lightbulb:] **Key Insights**")

            total_n = int(agg_sku["n"].sum())
            total_m = float(agg_sku["sum_nmc_m"].sum())
            top_row = agg_sku.iloc[0]
            top_pn = top_row["catalog_pn"]
            top_n = int(top_row["n"])
            top_m = float(top_row["sum_nmc_m"])
            top_money_share = (top_m / total_m * 100) if total_m > 0 else 0.0
            top_count_share = (top_n / total_n * 100) if total_n > 0 else 0.0

            st.markdown(
                f"{top_pn} — {top_money_share:.0f}% денег при "
                f"{top_count_share:.0f}% тендеров: главный SKU по выручке"
            )

            hot = agg_sku[agg_sku["catalog_pn"] != "Прочее"]
            if not hot.empty:
                hottest = hot.sort_values("n", ascending=False).iloc[0]
                if int(hottest["n"]) >= 2:
                    st.markdown(
                        f"{hottest['catalog_pn']} встретился {int(hottest['n'])} раз — "
                        f"самый повторяющийся part number"
                    )

            single = agg_sku[(agg_sku["n"] == 1) & (agg_sku["catalog_pn"] != "Прочее")]
            if len(single) >= 2:
                st.markdown(
                    f"{len(single)} SKU встретились только 1 раз — "
                    f"длинный хвост разовых позиций"
                )

            if len(agg_sku) >= 3 and total_m > 0:
                top3_money_share = float(agg_sku.head(3)["sum_nmc_m"].sum()) / total_m * 100
                if top3_money_share >= 70:
                    st.markdown(
                        f"Топ-3 SKU = {top3_money_share:.0f}% всех денег — "
                        f"узкий профиль продаж"
                    )

