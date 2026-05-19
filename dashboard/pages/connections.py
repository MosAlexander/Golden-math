from __future__ import annotations

import pandas as pd
import streamlit as st

st.markdown("## :primary[:material/cable:] Подключения")
st.caption("Состояние внешних интеграций и движка матчинга")

# ── Блок 1: Источники тендеров ────────────────────────────────────────────────

with st.container(border=True):
    head_col, badge_col = st.columns([5, 1])
    with head_col:
        st.markdown("#### :primary[:material/inbox:] Источники тендеров")
        st.caption("Откуда приходят тендеры на матчинг")
    with badge_col:
        st.markdown(":primary-background[:primary[Gate 8]]")

    with st.container(border=True):
        col_name, col_status = st.columns([4, 1])
        with col_name:
            st.markdown("**TenderGuru API**")
        with col_status:
            st.markdown(":red-background[:red[:material/cancel: Отключено]]")

        st.markdown(
            "**Эндпоинт:** _не настроен_  \n"
            "**Последний sync:** —  \n"
            "**Тендеров за сегодня:** —  \n"
            "**Подписки ОКПД2:** `26.11, 26.12, 26.20, 26.51, 27.11, 27.12`"
        )

    st.info(
        "Интеграция с TenderGuru запланирована на Gate 8. "
        "Сейчас система работает на seed-батче из 14 тендеров "
        "(`src/test_tenders.py`).",
        icon=":material/info:",
    )

# ── Блок 2: Каталог Radal ─────────────────────────────────────────────────────

with st.container(border=True):
    st.markdown("#### :primary[:material/database:] Каталог Radal")
    st.caption("Источник SKU для матчинга")

    with st.container(border=True):
        col_name, col_status = st.columns([4, 1])
        with col_name:
            st.markdown("**Seed-каталог**")
        with col_status:
            st.markdown(":orange-background[:orange[:material/warning: Заглушка]]")

        st.markdown(
            "**Источник:** seed-данные из репозитория  \n"
            "**Позиций:** 15  \n"
            "**Реальный каталог Radal:** _не подключён_  \n"
            "**Расписание обновления:** _будет согласовано с клиентом_"
        )

    st.info(
        "Сейчас матчинг идёт против **15 позиций seed-каталога**. "
        "Подключение к реальному каталогу Radal (формат уточняется) — "
        "на этапе onboarding после Gate 8.",
        icon=":material/info:",
    )

# ── Блок 3: Движок матчинга ───────────────────────────────────────────────────

with st.container(border=True):
    st.markdown("#### :primary[:material/memory:] Движок матчинга")
    st.caption("Какой алгоритм считает score для пар тендер–SKU")

    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            col_name, col_status = st.columns([4, 1])
            with col_name:
                st.markdown("**Rule-based (fallback)**")
            with col_status:
                st.markdown(":green-background[:green[:material/check_circle: Активен]]")

            st.markdown(
                "**Модуль:** `_calculate_score`  \n"
                "**Accuracy:** 9 / 14 на seed-данных"
            )

    with col_right:
        with st.container(border=True):
            col_name, col_status = st.columns([4, 1])
            with col_name:
                st.markdown("**Splink + DuckDB**")
            with col_status:
                st.markdown(":gray-background[:gray[:material/radio_button_unchecked: Не активен]]")

            try:
                import splink
                splink_version = splink.__version__
            except ImportError:
                splink_version = None

            version_line = (
                f"`{splink_version}` установлен"
                if splink_version
                else "_не установлен_"
            )
            st.markdown(
                f"**Версия:** {version_line}  \n"
                "**Blocking:** 4 правила (PN prefix, MFR+cat, V+cat, cat)"
            )

    st.info(
        "Сейчас активен встроенный rule-based движок. "
        "Переключение пайплайна на Splink запланировано на Gate 9 "
        "после калибровки порогов (DECISIONS.md §3, Слой 4).",
        icon=":material/info:",
    )

# ── Блок 4: LLM-судья ────────────────────────────────────────────────────────

with st.container(border=True):
    head_col, badge_col = st.columns([5, 1])
    with head_col:
        st.markdown("#### :primary[:material/psychology:] LLM-судья")
        st.caption("Резервный аналитик для borderline-кейсов (0.75 ≤ score < 0.92)")
    with badge_col:
        st.markdown(":primary-background[:primary[Gate 8]]")

    col_provider, col_key = st.columns(2)
    with col_provider:
        st.selectbox(
            "Провайдер",
            options=["GigaChat Max", "YandexGPT"],
            index=0,
            disabled=True,
            key="llm_provider",
        )
    with col_key:
        st.text_input(
            "API ключ",
            value="",
            type="password",
            disabled=True,
            key="llm_api_key",
        )

    col_timeout, col_fallback = st.columns(2)
    with col_timeout:
        st.markdown("**Таймаут:** 5 сек")
    with col_fallback:
        st.markdown("**Fallback при таймауте:** ручная очередь")

    st.caption(
        "LLM-судья будет подключён в Gate 8. До этого borderline-кейсы "
        "(0.75 ≤ score < 0.92) выводятся в Ленте с пометкой **«На проверку»**."
    )

# ── Блок 5: Настройка каналов ─────────────────────────────────────────────────

with st.container(border=True):
    head_col, badge_col = st.columns([5, 1])
    with head_col:
        st.markdown("#### :primary[:material/forum:] Настройка каналов")
        st.caption("Инфраструктура отправки уведомлений — кредс и адреса")
    with badge_col:
        st.markdown(":primary-background[:primary[Gate 8]]")

    channels_df = pd.DataFrame([
        {"Канал": "Telegram",   "Статус": "— не настроен", "Параметры": "bot_token, chat_id"},
        {"Канал": "Email SMTP", "Статус": "— не настроен", "Параметры": "smtp_host, port, user, password"},
        {"Канал": "Webhook",    "Статус": "— не настроен", "Параметры": "url, headers, signing_secret"},
    ])
    st.dataframe(
        channels_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Канал":     st.column_config.TextColumn(width="small"),
            "Статус":    st.column_config.TextColumn(width="small"),
            "Параметры": st.column_config.TextColumn(width="large"),
        },
    )

    st.caption(
        "Конфигурация каналов будет доступна в Gate 8. На странице "
        "**Настройки — Уведомления** уже сейчас видно, какие каналы будут "
        "включаемыми; на этой странице — где задаются их адреса и кредс."
    )
