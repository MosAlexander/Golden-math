from __future__ import annotations

import datetime

import altair as alt
import pandas as pd
import streamlit as st

from src.splink_config import (
    THRESHOLD_AUTO_MATCH,
    THRESHOLD_BORDERLINE_LOW,
    WEIGHT_PN_EXACT,
    WEIGHT_MFR,
    WEIGHT_PN_MFR_BONUS,
    WEIGHT_CATEGORY,
    WEIGHT_VOLTAGE_EXACT,
    WEIGHT_CURRENT_EXACT,
    WEIGHT_DESCRIPTION,
)
from dashboard.chart_utils import (
    COLOR_AUTO,
    COLOR_BORDERLINE,
    COLOR_REJECT,
    COLOR_RELEVANCE_MATCH,
    COLOR_RELEVANCE_STOCK,
    COLOR_RELEVANCE_MARGIN,
    COLOR_RELEVANCE_DEADLINE,
)

# Соответствует calculate_relevance() в src/splink_config.py.
# При изменении формулы синхронно обновить четыре места:
#   1. src/splink_config.py::calculate_relevance
#   2. dashboard/pages/matching.py::_decompose_relevance
#   3. dashboard/pages/matching.py — captions блока «Формула relevance»
#   4. этот кортеж
_RELEVANCE_WEIGHTS = [
    ("Match quality", 0.40, COLOR_RELEVANCE_MATCH),
    ("Stock",         0.25, COLOR_RELEVANCE_STOCK),
    ("Margin",        0.20, COLOR_RELEVANCE_MARGIN),
    ("Deadline",      0.15, COLOR_RELEVANCE_DEADLINE),
]

# ── Заголовок ─────────────────────────────────────────────────────────────────

st.markdown("## :primary[:material/settings:] Настройки")
st.caption("Конфигурация порогов, весов и расписания пайплайна")

# ── Блок 1: Пороги принятия решения ──────────────────────────────────────────

with st.container(border=True):
    st.markdown("#### :primary[:material/tune:] Пороги принятия решения")
    st.caption("Будущий UI — слайдеры заблокированы до калибровки на Splink (Gate 9)")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.slider(
            "Auto-match (≥)",
            min_value=0.50,
            max_value=1.00,
            value=THRESHOLD_AUTO_MATCH,
            step=0.01,
            disabled=True,
            key="th_auto",
        )
        st.caption("Совпадение принимается автоматически")

    with col2:
        st.slider(
            "Borderline (≥)",
            min_value=0.50,
            max_value=1.00,
            value=THRESHOLD_BORDERLINE_LOW,
            step=0.01,
            disabled=True,
            key="th_borderline",
        )
        st.caption("На проверку LLM или менеджеру")

    with col3:
        st.slider(
            "Reject (<)",
            min_value=0.50,
            max_value=1.00,
            value=THRESHOLD_BORDERLINE_LOW,
            step=0.01,
            disabled=True,
            key="th_reject",
        )
        st.caption("Совпадение отклоняется")

    st.info(
        "Значения зафиксированы в `src/splink_config.py`. "
        "Редактирование появится после Gate 9 (калибровка на Splink).",
        icon=":material/info:",
    )

# ── Блок 2: Веса факторов в score ─────────────────────────────────────────────

with st.container(border=True):
    st.markdown("#### :primary[:material/balance:] Веса факторов в score")
    st.caption("7 факторов из splink_config._calculate_score — сумма 105% за счёт PN+MFR бонуса")

    # Значения умножены на 100 для корректного отображения в ProgressColumn
    # с format="%.0f%%" (printf-формат ожидает число в диапазоне 0–100)
    weights_df = pd.DataFrame([
        {"Фактор": "PN exact match",       "Вес": WEIGHT_PN_EXACT * 100},
        {"Фактор": "Производитель (MFR)",  "Вес": WEIGHT_MFR * 100},
        {"Фактор": "PN + MFR бонус",       "Вес": WEIGHT_PN_MFR_BONUS * 100},
        {"Фактор": "Категория",            "Вес": WEIGHT_CATEGORY * 100},
        {"Фактор": "Напряжение (V)",       "Вес": WEIGHT_VOLTAGE_EXACT * 100},
        {"Фактор": "Ток (A)",              "Вес": WEIGHT_CURRENT_EXACT * 100},
        {"Фактор": "Описание (overlap)",   "Вес": WEIGHT_DESCRIPTION * 100},
    ])

    st.dataframe(
        weights_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Фактор": st.column_config.TextColumn(width="medium"),
            "Вес": st.column_config.ProgressColumn(
                format="%.0f%%",
                min_value=0.0,
                max_value=60,  # PN — самый большой, нормируемся к нему
            ),
        },
    )

# ── Блок 3: Формула relevance ─────────────────────────────────────────────────

with st.container(border=True):
    st.markdown("#### :primary[:material/percent:] Формула relevance")
    st.caption("Используется для сортировки тендеров в Ленте, не для решения auto/borderline/reject")

    rel_df = pd.DataFrame([
        {"Компонент": name, "Вес": w, "Доля": f"{int(w * 100)}%"}
        for name, w, _ in _RELEVANCE_WEIGHTS
    ])
    rel_colors = [c for _, _, c in _RELEVANCE_WEIGHTS]
    rel_domain = [name for name, _, _ in _RELEVANCE_WEIGHTS]

    rel_chart = (
        alt.Chart(rel_df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "Вес:Q",
                axis=alt.Axis(format="%", title=None),
                scale=alt.Scale(domain=[0, 0.5]),
            ),
            y=alt.Y(
                "Компонент:N",
                sort=rel_domain,
                axis=alt.Axis(title=None, labelLimit=0),
            ),
            color=alt.Color(
                "Компонент:N",
                scale=alt.Scale(domain=rel_domain, range=rel_colors),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Компонент:N"),
                alt.Tooltip("Доля:N", title="Вес"),
            ],
        )
        .properties(height=140)
    )
    st.altair_chart(rel_chart, use_container_width=True)

    st.caption(
        "Match quality — качество матча тендер–SKU. "
        "Stock — наличие на складе. "
        "Margin — потенциальная маржа по НМЦ. "
        "Deadline — близость дедлайна (срочные выше)."
    )

# ── Блок 4: Уведомления (disabled-заглушка) ───────────────────────────────────

with st.container(border=True):
    head_col, badge_col = st.columns([5, 1])
    with head_col:
        st.markdown("#### :primary[:material/notifications:] Уведомления")
        st.caption("Каналы рассылки авто-матчей")
    with badge_col:
        st.markdown(":primary-background[:primary[Gate 8]]")

    st.checkbox("Telegram — @radal_bot", value=False, disabled=True, key="notif_tg")
    st.checkbox("Email — ops@radal.ru",  value=False, disabled=True, key="notif_email")

    st.caption("Уведомления будут доступны в Gate 8 после интеграции с Telegram Bot API.")

# ── Блок 5: Расписание пайплайна (disabled-заглушка) ──────────────────────────

with st.container(border=True):
    head_col2, badge_col2 = st.columns([5, 1])
    with head_col2:
        st.markdown("#### :primary[:material/schedule:] Расписание пайплайна")
        st.caption("Регулярный запуск матчинга по новым тендерам")
    with badge_col2:
        st.markdown(":primary-background[:primary[Gate 8]]")

    col_freq, col_time = st.columns(2)
    with col_freq:
        st.selectbox(
            "Частота",
            options=["Ежедневно", "Раз в час", "Вручную"],
            index=0,
            disabled=True,
            key="sched_freq",
        )
    with col_time:
        st.time_input(
            "Время запуска",
            value=datetime.time(9, 0),
            disabled=True,
            key="sched_time",
        )

    st.caption("Регулярный запуск будет доступен в Gate 8 после интеграции с TenderGuru API.")
