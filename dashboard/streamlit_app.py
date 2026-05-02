"""streamlit_app.py — точка входа дашборда GoldenMatch Pro.

Только навигация и статус подключений. Никакого контента страниц —
весь контент живёт в pages/.
"""
from __future__ import annotations

import streamlit as st

# ПЕРВЫЙ вызов — до всего остального. Иначе Streamlit ругается.
st.set_page_config(
    page_title="GoldenMatch Pro",
    page_icon=":material/precision_manufacturing:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Все страницы относительно dashboard/streamlit_app.py
pages = {
    "📊 Мониторинг": [
        st.Page("pages/overview.py",    title="Обзор",          icon=":material/dashboard:",      default=True),
        st.Page("pages/tender_feed.py", title="Лента тендеров", icon=":material/list_alt:"),
        st.Page("pages/matching.py",    title="Матчинг",        icon=":material/compare_arrows:"),
    ],
    "📦 Данные": [
        st.Page("pages/catalog.py",     title="Каталог SKU",    icon=":material/inventory:"),
        st.Page("pages/win_loss.py",    title="Win/Loss",       icon=":material/emoji_events:"),
    ],
    "📈 Аналитика": [
        st.Page("pages/drill_down.py",  title="Drill Down",     icon=":material/query_stats:"),
    ],
    "⚙️ Система": [
        st.Page("pages/settings.py",    title="Настройки",      icon=":material/settings:"),
        st.Page("pages/connections.py", title="Подключения",    icon=":material/cable:"),
        st.Page("pages/faq.py",         title="FAQ",            icon=":material/help:"),
    ],
}

pg = st.navigation(pages)

# Sidebar — только навигация (выше) + статус подключений (ниже).
# Фильтры здесь запрещены — это правило CLAUDE.md.
with st.sidebar:
    st.divider()
    with st.container(border=True):
        st.caption("Подключения")
        st.markdown(":material/error: TenderGuru — не настроен")
        st.markdown(":material/error: B2B-Center — не настроен")
        st.markdown(":material/error: Splink — не установлен")

pg.run()
