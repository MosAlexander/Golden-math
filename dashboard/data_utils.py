"""data_utils.py — загрузка данных для дашборда.

Читает data/last_run.json. Если файла нет — запускает pipeline один раз.
Никогда не читать JSON напрямую в page-файлах — только через функции отсюда.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

CACHE_PATH = Path("data/last_run.json")


def _ensure_cache() -> None:
    """Если кэша нет — запускаем pipeline один раз.

    PYTHONIOENCODING=utf-8 не нужен: demo_pipeline.main() сам реконфигурирует
    sys.stdout/stderr на UTF-8 (см. шаг 4.0). check=True гарантирует, что
    мы упадём громко, если pipeline не сможет создать кэш.
    """
    if not CACHE_PATH.exists():
        subprocess.run(
            [sys.executable, "-m", "src.demo_pipeline"],
            check=True,
            capture_output=True,
        )


def _load_raw() -> dict:
    """Сырой dict из last_run.json. Внутренний хелпер."""
    _ensure_cache()
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


@st.cache_data
def load_pipeline_results() -> pd.DataFrame:
    """Результаты matching из последнего запуска pipeline."""
    return pd.DataFrame(_load_raw()["results"])


@st.cache_data
def load_catalog() -> pd.DataFrame:
    """Seed-каталог Radal (15 позиций)."""
    return pd.DataFrame(_load_raw()["catalog"])


@st.cache_data
def load_tenders() -> pd.DataFrame:
    """Тендеры с результатами matching (best_match_id, best_match_score)."""
    return pd.DataFrame(_load_raw()["tenders"])


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Агрегированные метрики для страницы Обзор.

    df — результат load_pipeline_results(). Возвращает счётчики
    по решениям + общее число уникальных тендеров.
    """
    if "decision" not in df.columns:
        return {"total": 0, "auto": 0, "borderline": 0, "reject": 0}
    return {
        "total":      int(df["tender_id"].nunique()) if "tender_id" in df.columns else 0,
        "auto":       int((df["decision"] == "auto").sum()),
        "borderline": int((df["decision"] == "borderline").sum()),
        "reject":     int((df["decision"] == "reject").sum()),
    }


def get_run_metadata() -> dict:
    """Метаданные последнего запуска (timestamp, accuracy)."""
    if not CACHE_PATH.exists():
        return {"timestamp": "—", "accuracy": "—"}
    raw = _load_raw()
    return {
        "timestamp": raw.get("timestamp", "—"),
        "accuracy":  raw.get("accuracy",  "—"),
    }
