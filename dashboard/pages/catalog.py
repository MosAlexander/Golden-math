"""catalog.py — Каталог SKU Radal (seed-данные, 15 позиций)."""
from __future__ import annotations

import streamlit as st

from dashboard.data_utils import load_catalog

# ── Заголовок страницы ─────────────────────────────────────────────────────
st.markdown("## :primary[:material/inventory:] Каталог SKU")
st.caption("Справочник компонентов Radal — seed-данные (15 позиций)")

st.info(":material/info: Seed-каталог (15 позиций). Будет заменён на выгрузку CSV из 1C.")

# ── Данные ──────────────────────────────────────────────────────────────────
df = load_catalog()

# ── KPI ─────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/leaderboard:] Показатели каталога")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего SKU", len(df))
    col2.metric("В наличии", int(df["in_stock"].sum()) if "in_stock" in df.columns else "—")
    col3.metric("Категорий", int(df["category"].nunique()) if "category" in df.columns else "—")
    col4.metric("Производителей", int(df["manufacturer"].nunique()) if "manufacturer" in df.columns else "—")

# ── Фильтры ──────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("#### :primary[:material/filter_list:] Фильтры")
    fc1, fc2, fc3, fc4 = st.columns(4)

    categories = ["Все"] + sorted(df["category"].dropna().unique().tolist()) if "category" in df.columns else ["Все"]
    manufacturers = ["Все"] + sorted(df["manufacturer"].dropna().unique().tolist()) if "manufacturer" in df.columns else ["Все"]
    stock_options = ["Все", "В наличии", "Нет в наличии"]

    sel_category = fc1.selectbox("Категория", categories, key="catalog_filter_category")
    sel_manufacturer = fc2.selectbox("Производитель", manufacturers, key="catalog_filter_manufacturer")
    sel_stock = fc3.selectbox("Наличие", stock_options, key="catalog_filter_stock")
    search_query = fc4.text_input("Поиск по PN / названию", key="catalog_search", placeholder="CM1000, Mitsubishi…")

# ── Применить фильтры ────────────────────────────────────────────────────────
filtered = df.copy()

if sel_category != "Все":
    filtered = filtered[filtered["category"] == sel_category]

if sel_manufacturer != "Все":
    filtered = filtered[filtered["manufacturer"] == sel_manufacturer]

if sel_stock == "В наличии":
    filtered = filtered[filtered["in_stock"] == True]  # noqa: E712
elif sel_stock == "Нет в наличии":
    filtered = filtered[filtered["in_stock"] == False]  # noqa: E712

if search_query.strip():
    q = search_query.strip().lower()
    mask = (
        filtered["part_number"].str.lower().str.contains(q, na=False)
        | filtered["name"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

# ── Таблица SKU ───────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown(f"#### :primary[:material/table_view:] Список SKU — {len(filtered)} позиций")

    display_cols = [c for c in ["id", "part_number", "manufacturer", "category", "name", "stock_qty", "in_stock"] if c in filtered.columns]

    col_cfg: dict = {}
    if "id" in filtered.columns:
        col_cfg["id"] = st.column_config.TextColumn("Артикул", width="small")
    if "part_number" in filtered.columns:
        col_cfg["part_number"] = st.column_config.TextColumn("Part Number", width="medium")
    if "manufacturer" in filtered.columns:
        col_cfg["manufacturer"] = st.column_config.TextColumn("Производитель", width="medium")
    if "category" in filtered.columns:
        col_cfg["category"] = st.column_config.TextColumn("Категория", width="small")
    if "name" in filtered.columns:
        col_cfg["name"] = st.column_config.TextColumn("Наименование", width="large")
    if "stock_qty" in filtered.columns:
        col_cfg["stock_qty"] = st.column_config.NumberColumn("На складе", format="%d шт.")
    if "in_stock" in filtered.columns:
        col_cfg["in_stock"] = st.column_config.CheckboxColumn("В наличии")

    selection = st.dataframe(
        filtered[display_cols].reset_index(drop=True),
        column_config=col_cfg,
        selection_mode="single-row",
        on_select="rerun",
        use_container_width=True,
        hide_index=True,
        key="catalog_table",
    )

# ── Карточка SKU (при выборе строки) ─────────────────────────────────────────
selected_rows = selection.selection.rows if selection and selection.selection else []

if selected_rows and selected_rows[0] < len(filtered):
    row_idx = selected_rows[0]
    sku = filtered.iloc[row_idx]
    pn = sku.get("part_number", "—")

    with st.container(border=True):
        st.markdown(f"#### :primary[:material/article:] Карточка SKU — {pn}")

        left, right = st.columns([1, 2])

        with left:
            st.caption("Ключевые параметры")
            st.markdown(f"**Part Number:** {sku.get('part_number', '—')}")
            st.markdown(f"**Производитель:** {sku.get('manufacturer', '—')}")
            st.markdown(f"**Категория:** {sku.get('category', '—')}")
            st.markdown(f"**Артикул:** {sku.get('id', '—')}")
            stock_qty = sku.get("stock_qty", 0)
            in_stock = sku.get("in_stock", False)
            st.markdown(f"**На складе:** {stock_qty} шт.")
            if in_stock:
                st.success("В наличии")
            else:
                st.error("Нет в наличии")

        with right:
            st.caption("Наименование")
            st.markdown(sku.get("name", "—"))

            params = sku.get("params", {})
            if isinstance(params, dict) and params:
                st.caption("Технические параметры")
                for key, val in params.items():
                    st.markdown(f"**{key}:** {val}")
