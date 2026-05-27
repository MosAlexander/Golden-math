"""streamlit_app.py — точка входа дашборда GoldenMatch Pro.

Только навигация и статус подключений. Никакого контента страниц —
весь контент живёт в pages/.
"""
from __future__ import annotations

import os

import streamlit as st

# ПЕРВЫЙ вызов — до всего остального. Иначе Streamlit ругается.
st.set_page_config(
    page_title="GoldenMatch Pro",
    page_icon=":material/precision_manufacturing:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Мост secrets→environ: если токен задан в .streamlit/secrets.toml,
# но ещё не попал в os.environ — прокидываем его, чтобы src/telegram_alerts.py
# мог читать через os.environ без зависимости от streamlit.
try:
    if "TELEGRAM_BOT_TOKEN" in st.secrets and "TELEGRAM_BOT_TOKEN" not in os.environ:
        os.environ["TELEGRAM_BOT_TOKEN"] = st.secrets["TELEGRAM_BOT_TOKEN"]
except Exception:
    pass

try:
    if "smtp" in st.secrets:
        for _smtp_key, _smtp_val in st.secrets["smtp"].items():
            env_key = f"SMTP_{_smtp_key.upper()}"
            if env_key not in os.environ:
                os.environ[env_key] = str(_smtp_val)
except Exception:
    pass

# Все страницы относительно dashboard/streamlit_app.py
pages = {
    "📊 Мониторинг": [
        st.Page("pages/overview.py",    title="Обзор",          icon=":material/dashboard:",      default=True),
        st.Page("pages/tender_feed.py", title="Лента тендеров", icon=":material/list_alt:"),
        st.Page("pages/matching.py",    title="Матчинг",        icon=":material/compare_arrows:"),
    ],
    "📦 Данные": [
        st.Page("pages/catalog.py",     title="Каталог SKU",       icon=":material/inventory:"),
        st.Page("pages/win_loss.py",    title="Разбор тендеров",   icon=":material/analytics:"),
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
