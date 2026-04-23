# Streamlit Design Patterns — GoldenMatch Pro

Rules and constraints for building Streamlit dashboard pages.
Extracted from a production multi-page survey dashboard, adapted for
a tender-matching system (electronics components, Splink matching engine, dark theme).

---

## Page Config

- Always call `st.set_page_config()` **before any other Streamlit call**, including imports that trigger st calls.
- Always use `layout="wide"` — narrow layout wastes space on data dashboards.
- Always use `initial_sidebar_state="expanded"`.
- Use Material Design icons via `:material/icon_name:` syntax for `page_icon`.

```python
st.set_page_config(
    page_title="GoldenMatch Pro",
    page_icon=":material/precision_manufacturing:",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

---

## Multi-Page Navigation

- Use `st.navigation()` with a dict of grouped sections — keys become section labels in the nav.
- Register pages with `st.Page("pages/filename.py", title="...", icon=":material/icon:")`.
- Set `default=True` on the home page (Обзор).
- Keep the entry point (`streamlit_app.py`) focused on: page_config → data loading → navigation definition → `pg.run()`.
- Never put page content in `streamlit_app.py` — only navigation wiring.

### Page Structure (4 groups, 9 pages)

```python
pages = {
    "📊 Мониторинг": [
        st.Page("pages/overview.py", title="Обзор", icon=":material/dashboard:", default=True),
        st.Page("pages/tender_feed.py", title="Лента тендеров", icon=":material/list_alt:"),
        st.Page("pages/matching.py", title="Матчинг", icon=":material/compare_arrows:"),
    ],
    "📦 Данные": [
        st.Page("pages/catalog.py", title="Каталог SKU", icon=":material/inventory:"),
        st.Page("pages/win_loss.py", title="Win/Loss", icon=":material/emoji_events:"),
    ],
    "📈 Аналитика": [
        st.Page("pages/drill_down.py", title="Drill Down", icon=":material/query_stats:"),
    ],
    "⚙️ Система": [
        st.Page("pages/settings.py", title="Настройки", icon=":material/settings:"),
        st.Page("pages/connections.py", title="Подключения", icon=":material/cable:"),
        st.Page("pages/faq.py", title="FAQ", icon=":material/help:"),
    ],
}
```

---

## Sidebar

- Sidebar contains **only navigation and connection status** — no global filters.
- All data filters are local to each page, placed in the main content area.
- Show API connection status at the bottom of the sidebar using `st.sidebar.container(border=True)`:

```python
with st.sidebar:
    # Navigation is rendered automatically by st.navigation()

    # Connection status at the bottom
    st.divider()
    with st.container(border=True):
        st.caption("Подключения")
        st.markdown(":material/check_circle: TenderGuru — Online")
        # or
        st.markdown(":material/error: B2B-Center — Offline")
```

---

## Local Filters (per-page)

- Place filters at the top of the page content area, not in the sidebar.
- Group filters in a single `st.container(border=True)` with columns inside.
- Use `st.columns()` to lay out 3–4 filters in one horizontal row.
- Show counts in filter options: `"IGBT (5)"` not `"IGBT"`.
- Implement "All" toggle logic: selecting "All" clears specific selections; selecting specifics removes "All".
- Use `label_visibility="collapsed"` on widgets inside labeled containers when the container or column header serves as the label.
- After filters change, recompute the filtered DataFrame and store in `st.session_state`.

---

## Session State Patterns

- Load raw data once into `st.session_state.df` with a guard: `if 'df' not in st.session_state`.
- Use `@st.cache_data` on all data loading functions — never load CSV on every rerender.
- Each page computes its own filtered view from the base data.
- For multiselects with "All" toggle, use paired state keys: `filter_role` + `_prev_filter_role` to detect toggle transitions.
- Reset filters by deleting state keys and calling `st.rerun()` — never by setting them to empty.
- **Avoid** `st.rerun()` except for explicit user actions (reset button) — it causes flicker.

---

## Layout: Columns, Containers, Sections

- Wrap every logical section in `st.container(border=True)`.
- Use `st.markdown("#### :primary[:material/icon:] Section Title")` for section headers inside containers.
- Use `st.columns(3)` or `st.columns(4)` for metric rows — equal columns for equal-weight items.
- Use `st.columns([3, 1])` for chart + insights layout — chart on left (3/4 width), insights on right.
- Use `st.columns([2, 1])` for form + result layout — controls on left, live output on right.
- Use `st.caption()` for chart descriptions, insights, and source attributions — never `st.write()` for explanatory text.
- Use `st.tabs()` for alternative views of the same data on a single page.

---

## Metrics

- Group 3–5 `st.metric()` calls in equal `st.columns()` inside a `st.container(border=True)`.
- Use `delta` to show relative context: `delta=f"{n/total*100:.1f}% of total"`.
- Use `delta_color="inverse"` when lower value = better outcome (e.g. firefighting rate, error rate).
- Truncate long metric labels: `label[:20] + "..."` if `len(label) > 20`.
- Use `st.progress(int(value))` beneath risk/score metrics to give visual weight.

---

## Decision Display Pattern

### In tables (`st.dataframe`)
- Use `st.column_config.ProgressColumn` for match% — renders a colored progress bar natively.
- Use `st.column_config.NumberColumn(format="%.1f%%")` for percentage display.
- Use `st.column_config.TextColumn` for decision text — plain text, no emoji markers.
- **Never** use emoji markers (✅, ⚠️, ❌) for statuses — anywhere in the application.

### In detail cards (Матчинг page)
- Use native Streamlit alert blocks for decision display:
  ```python
  if decision == "auto":
      st.success("Auto match — совпадение подтверждено")
  elif decision == "borderline":
      st.warning("Borderline → на проверку LLM / менеджеру")
  else:
      st.error("Rejected — совпадение не найдено")
  ```
- These alert blocks provide colored backgrounds natively: green, yellow, red.

---

## Color System

Define all colors as module-level constants in `chart_utils.py` — never hardcode hex in page files.

### Core Palette

```python
# UI
PRIMARY_COLOR = '#FF9800'       # Orange — UI accents, buttons, headers

# Match Decision
COLOR_AUTO = '#16a34a'          # Green — auto match (≥0.92)
COLOR_BORDERLINE = '#FACC15'    # Bright yellow — borderline (0.75–0.92)
COLOR_REJECT = '#EF4444'        # Red — rejected (<0.75)
COLOR_NEUTRAL = '#6B7280'       # Gray — no data, unavailable, inactive

# Scenario
COLOR_SCENARIO_A = '#3B82F6'    # Blue — exact PN match
COLOR_SCENARIO_B = '#8B5CF6'    # Purple — parametric match
COLOR_SCENARIO_C = '#6B7280'    # Gray — category only

# Reusable semantic mapping
COLOR_GOOD = COLOR_AUTO         # Green — in stock >10, on time
COLOR_WARNING = COLOR_BORDERLINE  # Yellow — stock 1–10, deadline approaching
COLOR_DANGER = COLOR_REJECT     # Red — out of stock, deadline ≤7d
COLOR_MUTED = COLOR_NEUTRAL     # Gray — no stock, deadline >7d, inactive

# Categorical rainbow (for categories: igbt, thyristor, plc_module, etc.)
RAINBOW_PALETTE = ['#8B5CF6', '#3B82F6', '#10B981', '#FACC15', '#F59E0B', '#EF4444']

# Binary comparison
COMPARE_PALETTE = ['#8B5CF6', '#F59E0B']
```

### Color Rules
- Use `RAINBOW_PALETTE` for categorical data (component categories), cycling by index.
- Use `COMPARE_PALETTE` for binary comparisons (e.g. in_stock vs out_of_stock).
- Use `PRIMARY_COLOR` for single-series charts.
- Use `:primary[text]` in Markdown for inline emphasis — it uses the theme's `primaryColor`.
- Stock/deadline colors reuse the semantic mapping: good/warning/danger/muted.

---

## Visualization: Altair Only

- Use **Altair** as the sole charting library — bar charts, lollipop charts, grouped bars, stacked bars, donut charts, diverging bars, heatmaps.
- Always call `st.altair_chart(chart, use_container_width=True)` — never set a fixed pixel width.
- Import colors from `chart_utils.py` — never hardcode hex values in page files.

### Altair Chart Conventions

- Always use `cornerRadiusEnd=4` on bar marks.
- Always set `axis=alt.Axis(labelLimit=0, labelLineHeight=12)` on Y axes with long category labels.
- Always include `tooltip` with category, count, and percentage (formatted `.1f`).
- Sort horizontal bars by `-x` (descending value): `sort='-x'`.
- Set `title=None` on axis encodings when the container already has a header.
- For multi-line labels, apply `wrap_labels(data, column, max_words_per_line=5)` before charting.
- Use `legend=None` when the Y-axis already labels the categories.
- Use `alt.Legend(title=None, orient='bottom', columns=2)` for donut/pie charts.
- Add a reference line with `alt.Chart(pd.DataFrame({'x': [avg]})).mark_rule(strokeDash=[5,5])`.
- For color encoding with domain-specific palettes, use `alt.Scale(domain=[...], range=[...])`.

### Color Mapping in Altair

```python
# Decision colors in Altair
decision_scale = alt.Scale(
    domain=["auto", "borderline", "reject"],
    range=[COLOR_AUTO, COLOR_BORDERLINE, COLOR_REJECT]
)

# Scenario colors in Altair
scenario_scale = alt.Scale(
    domain=["A", "B", "C"],
    range=[COLOR_SCENARIO_A, COLOR_SCENARIO_B, COLOR_SCENARIO_C]
)
```

---

## Data Pipeline Pattern

Follow this strict pipeline in every page:

```
Data source (CSV / API / session)
         ↓
  @st.cache_data load function
         ↓
  Derive boolean/list columns at load time
         ↓
  st.session_state.df (raw, unfiltered)
         ↓
  Page-local filters (top of page content)
         ↓
  Filtered DataFrame
         ↓
  Aggregate (value_counts / groupby / crosstab / pivot)
         ↓
  chart_utils function → st.altair_chart
```

- Derive boolean flags at load time, not per page.
- Derive list columns at load time for comma-separated multi-value fields.
- Always load data through a utility function — never read CSV directly in page files.

---

## Insights Panel Pattern

For every major chart, use a `[3, 1]` column split:

- Left column (3): chart with `use_container_width=True`.
- Right column (1): `st.markdown("##### :primary[:material/lightbulb:] Key Insights")` followed by `st.caption()` calls.
- Insights must be **computed from data** — reference actual values, not static text.
- Use conditional logic to switch insight text based on data direction (positive/negative delta, above/below average).

---

## Comparison / Cohort Pattern

For split-cohort analysis:

1. Split into two DataFrames by boolean column.
2. Compute the same metric for both groups.
3. Calculate `delta = group_a_value - group_b_value`.
4. Display with `st.metric(delta=f"{delta:+.0f}pp")`.
5. Add narrative in `st.caption()`: reference computed values, not static text.

---

## Ordered Categorical Data

- Define sort orders as module-level constants:
  ```python
  DECISION_ORDER = ["auto", "borderline", "reject"]
  SCENARIO_ORDER = ["A", "B", "C"]
  ```
- Pass sort order to chart functions to maintain logical sequence on axes.
- Pass `order` to filter option generators to maintain logical sort in dropdowns.

---

## Theme

```toml
# .streamlit/config.toml
[theme]
base = "dark"
primaryColor = "#FF9800"
```

- Dark base theme — all pages must look correct on dark backgrounds.
- `primaryColor = "#FF9800"` drives `:primary[...]` inline highlights and widget accents.
- No custom CSS — use `border=True` containers, `:primary[...]` emphasis, and Material icons.
- Verify that all chart colors (`COLOR_AUTO`, `COLOR_BORDERLINE`, etc.) are legible on dark backgrounds.

---

## Antipatterns — Avoid These

### General
- **Avoid** loading data inside page files — always use cached utility functions.
- **Avoid** `st.write()` for explanatory text — use `st.markdown()` or `st.caption()`.
- **Avoid** hardcoding chart colors in page files — always import from `chart_utils`.
- **Avoid** `st.columns([1,1,1,1,1])` for 5-metric rows — use `st.columns(5)` shorthand.
- **Avoid** `st.rerun()` except for explicit user actions (reset button) — it causes flicker.
- **Avoid** showing raw `st.dataframe()` tables without `column_config` — always configure columns.

### Strictly Prohibited
- **Never** use emoji markers (✅, ⚠️, ❌, 🔴, 🟢, 🟡) for statuses or labels — anywhere.
- **Never** use `unsafe_allow_html=True` — only native Streamlit components and Altair.
- **Never** use custom HTML/CSS injected via `st.markdown()` — only native Streamlit styling.
- **Never** put global filters in the sidebar — sidebar is for navigation and connection status only.
- **Never** put page content in `streamlit_app.py` — only navigation wiring.
