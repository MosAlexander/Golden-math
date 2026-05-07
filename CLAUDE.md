# GoldenMatch Pro — Tender Matching for Electronics

## Что это
Cross-matching система: тендеры на электронные компоненты ↔ каталог дистрибьютора Radal.
Ядро: Part Number extraction + Splink probabilistic matching + LLM-judge.

## Клиент
Radal Микроэлектроника (ООО Радал, ИНН 2634101203, Ставрополь).
Оптовая поставка электронных компонентов: IGBT, тиристоры, ПЛИС, PLC-модули.

## Стек
- Python 3.11+, FastAPI, Splink + DuckDB, PostgreSQL
- Dashboard: Streamlit (dark theme, Altair charts)
- Alerts: Telegram Bot API (интегрирован в дашборд)
- LLM-judge: GigaChat Max / YandexGPT (borderline zone only)

## Структура проекта
- `src/` — весь production-код (matching pipeline)
- `tests/` — pytest тесты, запуск: `pytest tests/ -v`
- `dashboard/` — Streamlit UI (9 страниц, точка входа: `streamlit_app.py`)
- `dashboard/chart_utils.py` — цвета и палитры, импортировать оттуда
- `docs/` — архитектура, решения, бизнес-правила

## Dashboard: 9 страниц в 4 группах
📊 Мониторинг: Обзор, Лента тендеров, Матчинг
📦 Данные: Каталог SKU, Win/Loss
📈 Аналитика: Drill Down (вход только из Win/Loss)
⚙️ Система: Настройки, Подключения, FAQ

## Архитектура: 7 слоёв
1. Data sources (TenderGuru, B2B-Center, Radal 1C CSV)
2. PN extraction + normalization (regex, не NLP)
3. Scenario router (A: exact PN 70%, B: parametric 20%, C: category 10%)
4. Splink matching (PN:60%, MFR:20%, Params:15%, Desc:5%)
5. LLM-judge (только borderline 0.75–0.92, timeout 5s → manual queue)
6. Relevance ranking (Match 40% + Stock 25% + Margin 20% + Deadline 15%)
7. Dashboard + Telegram alerts

## Критические бизнес-правила (нарушение = баг)
- Part Number — главный ключ. Exact match, НЕ fuzzy.
- PN + Manufacturer = уникальная пара. Один PN от разных MFR = разные компоненты.
- Пороги: ≥0.92 auto, 0.75–0.92 borderline → LLM, <0.75 reject.
- Precision > Recall при калибровке.
- LLM-judge НИКОГДА для auto (≥0.92) и reject (<0.75).
- Пайплайн НИКОГДА не ломается из-за LLM (fallback → manual queue).

## Нормализация PN
- Uppercase: `cm1000e3u-34nf` → `CM1000E3U-34NF`
- Убрать пробелы: `6ES7 321-1BL00-0AA0` → `6ES7321-1BL00-0AA0`
- Слэши → дефисы: `SKKT162/16E` → `SKKT162-16E`
- Strip packaging suffixes: `-ND`, `-TR`, `-CT`, `-NOPB`, `-PBF`
- Разные ревизии (-1 vs -2) — РАЗНЫЕ компоненты, НЕ стрипать

## Код-конвенции
- Type hints во всех функциях
- Docstrings на русском (описание) + английском (параметры)
- `from __future__ import annotations` в каждом файле
- Dataclasses для структур данных
- Тесты: pytest, naming: `test_<module>_<what>_<scenario>`
- Никаких print() в production-коде, только logging

## Dashboard-конвенции
- При работе с дашбордом — читай `.claude/skills/streamlit-design-patterns/SKILL.md`
- Цвета ТОЛЬКО из `dashboard/chart_utils.py` — никогда не хардкодить hex в страницах
- Графики: Altair по умолчанию, `st.altair_chart(chart, use_container_width=True)`. Исключение: Plotly (`st.plotly_chart`) разрешён только для radar (Scatterpolar), waterfall (go.Waterfall), sankey и sunburst — типов, недоступных в Altair.
- Sidebar: только навигация + статус API, фильтры локальные на каждой странице
- Запрещено: эмодзи-маркеры для статусов, unsafe_allow_html, кастомный CSS

## Что УДАЛЕНО и не должно появляться
- Всё про трубы, металлопрокат, ГОСТ, материалы, размеры
- Natasha как ядро нормализации
- Словарь "ст." → "сталь", regex "108х4"
- NormalizedRecord с полями gost, material, dimensions

## Команды
- `pytest tests/ -v` — запуск тестов
- `python -m src.demo_pipeline` — полный пайплайн
- `streamlit run dashboard/streamlit_app.py` — дашборд

## При работе с кодом
- Всегда читай docs/RULES.md перед изменением matching-логики
- Всегда читай docs/DECISIONS.md перед архитектурными решениями
- При работе с дашбордом — читай SKILL.md в .claude/skills/streamlit-design-patterns/
- После изменений в normalizer — запускай demo_pipeline для валидации
- Seed-каталог (15 позиций) — временный, будет заменён на CSV из 1C
