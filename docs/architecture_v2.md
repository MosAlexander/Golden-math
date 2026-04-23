# GoldenMatch Pro — Финальная архитектура v2

> Визуализация: `radal_goldenmatch_architecture_v2.html` (SVG, открывается в браузере)

## Поток данных

```
TenderGuru ──┐
             │
B2B-Center ──┼──→ [PN Extract + Normalize] ──→ [Scenario Router A/B/C]
             │
Radal 1C ────┘
                         │
                         ▼
                  [Splink Matching]
                  PN:60% MFR:20% Params:15% Desc:5%
                         │
                         ▼
               ┌─────────┴─────────┐
               │                   │
          ≥0.92: Auto        0.75–0.92: LLM-judge
               │                   │
               └─────────┬─────────┘
                         │
                         ▼
                 [Relevance Ranking]
                 Match 40% + Stock 25% + Margin 20% + Deadline 15%
                         │
                         ▼
              [Dashboard + Telegram Alerts]
```

## Слои

1. **Data sources** — TenderGuru (ОКПД2 26.x/27.x), B2B-Center, Radal 1C CSV
2. **Normalization** — PN extractor (regex+stopwords), MFR detector (200+ aliases), Param extractor (V/A/W/MHz)
3. **Scenario router** — A: PN exact ~70%, B: Parametric ~20%, C: Category ~10%
4. **Splink matching** — Fellegi-Sunter, 4 blocking rules, 6 comparison fields, EM-trained weights
5. **LLM-judge** — GigaChat/YandexGPT, borderline 0.75–0.92 only, 5s timeout fallback
6. **Relevance ranking** — Match 40% + Stock 25% + Margin 20% + Deadline 15%
7. **Dashboard + alerts** — Streamlit/HTML (4 screens) + Telegram bot
