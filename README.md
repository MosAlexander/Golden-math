# GoldenMatch Pro — Tender Matching for Radal

Модуль cross-matching тендеров на электронные компоненты с каталогом дистрибьютора [Radal Микроэлектроника](https://radal.ru).

Ядро: **Part Number extraction** + **Splink probabilistic matching** + **LLM-judge** для borderline-зоны.

## Быстрый старт

```bash
# 1. Установка
pip install -r requirements.txt

# 2. Запуск полного пайплайна (seed-данные, без Splink — fallback scoring)
python -m src.demo_pipeline

# 3. Запуск со Splink (production)
pip install splink duckdb
python -m src.demo_pipeline

# 4. Dashboard (открыть в браузере)
open dashboard.html
```

## Структура проекта

```
goldenmatch-radal/
├── src/
│   ├── __init__.py                    # Пакет
│   ├── normalizer_electronics.py      # Ядро: PN extraction, MFR detection, scenario router
│   ├── domain_dict_electronics.py     # Словарь: 17 категорий, 200+ brand aliases, regex
│   ├── seed_catalog_radal.py          # 15 флагманских позиций Radal
│   ├── test_tenders.py                # 14 тестовых тендеров (сценарии A/B/C)
│   ├── splink_config.py               # Splink конфиг: blocking, weights, fallback, ranking
│   └── demo_pipeline.py               # Единая точка входа: end-to-end пайплайн
├── docs/
│   ├── DECISIONS.md                   # Архитектурные решения, стек, таймлайн
│   ├── RULES.md                       # Бизнес-правила, пороги, что удалено/оставлено
│   └── diagrams/
│       └── architecture_v2.md         # Описание 7-слойной архитектуры
├── dashboard.html                     # HTML дашборд (zero dependencies)
├── radal_goldenmatch_architecture_v2.html  # SVG-диаграмма архитектуры
├── requirements.txt
└── README.md
```

## Архитектура (7 слоёв)

```
[TenderGuru + B2B-Center + Radal 1C]
                │
    [PN Extract + MFR Detect + Params]
                │
        [Scenario Router A/B/C]
         70%    20%    10%
                │
         [Splink Matching]
    PN:60%  MFR:20%  Params:15%  Desc:5%
                │
        ┌───────┴───────┐
    ≥0.92: Auto    0.75-0.92: LLM-judge
        └───────┬───────┘
       [Relevance Ranking]
  Match:40% Stock:25% Margin:20% Deadline:15%
                │
   [Dashboard + Telegram Alerts]
```

## Три сценария матчинга

| Сценарий | Доля | Условие | Пример |
|----------|------|---------|--------|
| **A** | ~70% | Part number в тексте | "Поставка IGBT CM1000E3U-34NF Mitsubishi" |
| **B** | ~20% | Категория + параметры | "IGBT-модуль 600В 75А для ЧРП" |
| **C** | ~10% | Общее описание | "Поставка электронных компонентов Siemens" |

## Замена seed-каталога на реальный

Когда получишь CSV из 1C Radal — замени содержимое `seed_catalog_radal.py`, перекалибруй: `python -m src.demo_pipeline`

## Клиент

- **Radal Микроэлектроника** (ООО Радал, ИНН 2634101203)
- Ставрополь / Москва
- radal.ru
- Основной заказчик в тендерах: НПО «Центротех»

## Telegram-уведомления

Бот настраивается через раздел **Подключения → Telegram Bot API** в дашборде. Токен хранится в `.streamlit/secrets.toml` (не коммитится, шаблон — `secrets.toml.example`). Каналы получателей и события настраиваются через UI, хранятся в `data/channels.json`. Подробнее — [CLAUDE.md](CLAUDE.md).
