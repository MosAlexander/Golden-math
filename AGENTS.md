# GoldenMatch Pro — Agent Instructions

## Build & Test
```bash
pip install -r requirements.txt
pytest tests/ -v
python -m src.demo_pipeline
streamlit run dashboard/streamlit_app.py
```

## Architecture
7-layer pipeline: Data Sources → PN Normalization → Scenario Router →
Splink Matching → LLM Judge → Relevance Ranking → Dashboard.

## Key Constraints
- Part Number is THE primary key for matching electronics
- Never use fuzzy matching when exact PN is available
- Thresholds: ≥0.92 auto, 0.75–0.92 borderline, <0.75 reject
- Pipeline must NEVER break due to LLM failures
- This is electronics domain — no pipes, steel, GOST references

## Dashboard Constraints
- Streamlit only, dark theme, Altair charts only
- No emoji markers for statuses, no unsafe_allow_html, no custom CSS
- Colors only from dashboard/chart_utils.py
- Sidebar: navigation + API status only, no global filters

## Code Style
- Python 3.11+, type hints required
- Dataclasses for data structures
- pytest for testing
- No print() in production code
