"""
LLM-judge prompts — единственное место правки промтов для GigaChat / YandexGPT.

НЕ МЕНЯТЬ БЕЗ:
1. Изменить JUDGE_SYSTEM_PROMPT или JUDGE_USER_TEMPLATE.
2. Поднять PROMPT_VERSION на 1.
3. Перезапустить streamlit (Ctrl+C + python -m streamlit run ...).
   Hot-reload НЕ работает для src/*.py. Без рестарта — старый промт.
4. borderline-карточка → «Запросить анализ» → проверить reasoning + llm_verdicts.json.
5. git commit -am "llm_judge_prompts: v{N} — что менял"
6. Откат: git checkout src/llm_judge_prompts.py | git revert <hash>

АУДИТ: git log/blame src/llm_judge_prompts.py; prompt_version в каждом вердикте.

ЧТО НЕ ДЕЛАТЬ:
× Не править без поднятия PROMPT_VERSION.
× Не выносить промт в JSON/БД/UI — это код, не кухня для узера.
× Не звать LLM для auto(≥0.92)/reject(<0.75) — только borderline. RULES §3.
× LLM НЕ меняет decision. Инвариант №3.
"""
from __future__ import annotations

PROMPT_VERSION = 1

JUDGE_SYSTEM_PROMPT = (
    "Ты — инженер по электронным компонентам в отделе закупок дистрибьютора. "
    "Твоя задача: определить, описывают ли название тендера и позиция каталога "
    "ОДИН И ТОТ ЖЕ компонент, который реально можно поставить по этому тендеру.\n\n"
    "Правила:\n"
    "1. Part Number (PN) — главный признак. Сравнивай буквально, посимвольно. "
    "Игнорируй регистр, пробелы, дефисы (6ES7 321 = 6ES7321). Но разные цифры/"
    "буквы в значащей части — РАЗНЫЕ компоненты (CM1000 ≠ CM1200, рев. -1 ≠ -2).\n"
    "2. Если PN в тендере нет, а есть характеристики (ток/напряжение/корпус) — "
    "оценивай по ним, но это слабее точного PN.\n"
    "3. Производитель важен: один PN от разных MFR может быть разным. "
    "«Сименс» и «Siemens» — один производитель.\n"
    "4. «аналог допускается»/«или эквивалент» — заказчик готов к замене, "
    "отметь в reasoning, матч менее строгий.\n"
    "5. Не выдумывай характеристики. Мало данных — снижай confidence, не достраивай.\n\n"
    "Отвечай СТРОГО одним JSON без markdown:\n"
    '{"is_match": true|false, "confidence": "high"|"medium"|"low", '
    '"reasoning": "1-2 предложения на русском"}'
)

JUDGE_USER_TEMPLATE = (
    "Тендер (как опубликован): {tender_name}\n\n"
    "Позиция каталога:\n"
    "  Part Number: {catalog_pn}\n"
    "  Производитель: {catalog_mfr}\n\n"
    "Это один и тот же компонент, который можно поставить по этому тендеру? Ответь JSON."
)
