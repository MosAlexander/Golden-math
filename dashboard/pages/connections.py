from __future__ import annotations

import streamlit as st
from src.telegram_alerts import get_token, get_me, send_message
from src.channels_config import (
    load_config,
    save_config,
    add_channel,
    update_channel,
    delete_channel,
    toggle_channel,
    set_event,
    validate_chat_id,
    enabled_channels,
)

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

# ── Блок 5: Telegram Bot API ─────────────────────────────────────────────────

with st.container(border=True):
    token = get_token()
    me_result = get_me(token) if token else None

    head_col, badge_col = st.columns([5, 1], vertical_alignment="center")
    with head_col:
        st.markdown("#### :primary[:material/send:] Telegram Bot API")
        st.caption("Бот и каналы для уведомлений об участии в тендерах")
    with badge_col:
        if token and me_result and me_result["ok"]:
            st.markdown(":green-background[:green[Подключён]]")
        elif token:
            st.markdown(":red-background[:red[Ошибка токена]]")
        else:
            st.markdown(":gray-background[:gray[Не настроен]]")

    # ── Секция: токен (read-only индикатор) ──
    with st.container(border=True):
        col_msg, col_btn = st.columns([4, 1], vertical_alignment="center")
        with col_msg:
            if token:
                if me_result and me_result["ok"]:
                    st.success(
                        f"Бот @{me_result['bot_username']} — соединение успешно",
                        icon=":material/check_circle:",
                    )
                else:
                    err = me_result["error"] if me_result else "нет данных"
                    st.error(f"Ошибка соединения: {err}", icon=":material/error:")
            else:
                st.info(
                    "Токен не задан. Добавьте TELEGRAM_BOT_TOKEN в "
                    ".streamlit/secrets.toml (см. secrets.toml.example).",
                    icon=":material/info:",
                )
        with col_btn:
            if st.button(":material/rocket_launch: Тест", key="tg_test",
                         use_container_width=True):
                if not token:
                    st.toast("Токен не задан")
                else:
                    recheck = get_me(token)
                    if not recheck["ok"]:
                        st.toast(f"Ошибка токена: {recheck['error']}")
                    else:
                        test_channels = enabled_channels(load_config())
                        if not test_channels:
                            st.toast("Нет активных каналов — добавьте канал ниже.")
                        else:
                            sent, failed = [], []
                            for ch in test_channels:
                                res = send_message(
                                    token, ch["chat_id"],
                                    "🔔 <b>Тест GoldenMatch Pro</b> — бот работает корректно."
                                )
                                if res["ok"]:
                                    sent.append(ch["name"])
                                else:
                                    failed.append(f"{ch['name']}: {res.get('error', 'ошибка')}")
                            if sent:
                                st.toast(f"Отправлено в: {', '.join(sent)}", icon=":material/check_circle:")
                            for f in failed:
                                st.toast(f"Не доставлено — {f}", icon=":material/error:")

    # ── Секция: каналы получателей ──
    config = load_config()
    channels = config.get("channels", [])
    active_count = sum(1 for ch in channels if ch.get("enabled"))
    inactive_count = len(channels) - active_count

    with st.container(border=True):
        ch_head_col, ch_count_col = st.columns([5, 2], vertical_alignment="center")
        with ch_head_col:
            st.markdown("**Каналы получателей**")
        with ch_count_col:
            if channels:
                st.caption(f"{active_count} активных · {inactive_count} выключен")

        if not channels:
            st.caption(
                ":material/info: Каналов пока нет. Добавьте первый в форме ниже — "
                "после сохранения он появится здесь с переключателем и кнопками "
                "редактирования и удаления."
            )
        else:
            for channel in channels:
                ch_id = channel["id"]
                with st.container(border=True):
                    col_info, col_toggle, col_edit, col_del = st.columns(
                        [7, 1.2, 1, 1], vertical_alignment="center"
                    )
                    with col_info:
                        st.markdown(
                            f":material/group: **{channel['name']}**  \n"
                            f"&nbsp;&nbsp;&nbsp;&nbsp;:gray[:material/tag: {channel['chat_id']}]"
                        )
                    with col_toggle:
                        new_enabled = st.toggle(
                            "вкл",
                            value=channel["enabled"],
                            key=f"tg_toggle_{ch_id}",
                            label_visibility="collapsed",
                        )
                        if new_enabled != channel["enabled"]:
                            save_config(toggle_channel(config, ch_id, new_enabled))
                            st.rerun()
                    with col_edit:
                        if st.button("", icon=":material/edit:", key=f"tg_edit_{ch_id}",
                                     use_container_width=True):
                            st.session_state[f"tg_editing_{ch_id}"] = True
                            st.rerun()
                    with col_del:
                        if st.button("", icon=":material/delete:", key=f"tg_del_{ch_id}",
                                     use_container_width=True):
                            save_config(delete_channel(config, ch_id))
                            st.toast(f"Канал «{channel['name']}» удалён")
                            st.rerun()

                if st.session_state.get(f"tg_editing_{ch_id}"):
                    with st.container(border=True):
                        st.caption(f":material/edit: Редактирование «{channel['name']}»")
                        ef1, ef2 = st.columns(2)
                        with ef1:
                            new_name = st.text_input(
                                "Название", value=channel["name"], key=f"tg_ename_{ch_id}"
                            )
                        with ef2:
                            new_chat_id = st.text_input(
                                "Chat ID / @username", value=channel["chat_id"],
                                key=f"tg_echatid_{ch_id}"
                            )
                        esave_col, ecancel_col, _ = st.columns([1, 1, 3])
                        with esave_col:
                            save_clicked = st.button(
                                "Сохранить", key=f"tg_esave_{ch_id}",
                                type="primary", use_container_width=True
                            )
                        with ecancel_col:
                            if st.button("Отмена", key=f"tg_ecancel_{ch_id}",
                                         use_container_width=True):
                                st.session_state.pop(f"tg_editing_{ch_id}", None)
                                st.rerun()
                        if save_clicked:
                            try:
                                save_config(update_channel(
                                    config, ch_id, name=new_name, chat_id=new_chat_id
                                ))
                                st.session_state.pop(f"tg_editing_{ch_id}", None)
                                st.toast("Канал обновлён")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e), icon=":material/error:")

    # ── Секция: добавить канал ──
    with st.container(border=True):
        st.markdown("**Добавить канал**")
        with st.form("tg_add_form", clear_on_submit=True, border=False):
            add1, add2, add3 = st.columns([2, 2, 1], vertical_alignment="bottom")
            with add1:
                _name = st.text_input("Название", key="tg_new_name",
                                      placeholder="напр. Менеджеры")
            with add2:
                _chatid = st.text_input("Chat ID / @username", key="tg_new_chatid",
                                        placeholder="-100... или @канал")
            with add3:
                add_clicked = st.form_submit_button(":material/add: Добавить",
                                                    use_container_width=True)
        if add_clicked:
            try:
                save_config(add_channel(config, _name, _chatid))
                st.toast("Канал добавлен")
                st.rerun()
            except ValueError as e:
                st.error(str(e), icon=":material/error:")

    # ── Секция: когда отправлять ──
    with st.container(border=True):
        st.markdown("**Когда отправлять**")
        _events = [
            ("participate", "При решении «Участвовать»"),
            ("ask",         "При «Запросить мнение»"),
            ("skip",        "При «Пропустить»"),
        ]
        for ev_key, ev_label in _events:
            current = config["events"].get(ev_key, False)
            new_val = st.toggle(ev_label, value=current, key=f"tg_ev_{ev_key}")
            if new_val != current:
                save_config(set_event(config, ev_key, new_val))
                st.rerun()
