# GoldenMatch Pro — Sequential Agentic Workflow with Quality Gates (v2)

> Этот файл — единая точка восстановления workflow между сессиями.
> Агент читает его ПЕРВЫМ делом перед любым действием в проекте.
> После прохождения каждого gate — обновляет статус здесь.

> **v2 changelog (2026-04-30):** добавлен Gate 3.5 (E2E product invariants
> + T-A07 fix). Из Gate 9 удалён фикс T-A07 (мелкий стоп-лист, переехал
> в 3.5). В Gate 9 остаётся только то, что требует всей предыдущей
> инфраструктуры: безопасное переключение движка matching на Splink с
> использованием инвариантов из 3.5 как safety net.

---

## Текущий статус сессии

```
Gate 0   [✅ PASSED]  Project audit (verified 2026-04-30)
Gate 1   [✅ PASSED]  Core pipeline (src/)
Gate 2   [✅ PASSED]  Test suite — 284 passed, 1 xfailed
Gate 3   [✅ PASSED]  Matching engine + relevance ranking
Gate 3.5 [✅ PASSED]  E2E product invariants + T-A07 fix + okpd2 disentanglement
Gate 4   [✅ PASSED]      Pipeline cache + dashboard foundation
      4.0 ✅ PASSED — pipeline cache + UTF-8 stdout/stderr fix
      4.1 ✅ PASSED — dashboard/chart_utils.py
      4.2 ✅ PASSED — dashboard/data_utils.py
      4.3 ✅ PASSED — dashboard/streamlit_app.py
      4.4 ✅ PASSED — dashboard/pages/ заглушки (9 файлов)
Gate 5   [✅ PASSED]  Dashboard pages — Мониторинг (3 стр)
      5.1 ✅ PASSED — pages/overview.py (KPI + 3 chart блока)
      5.2 ✅ PASSED — pages/tender_feed.py (фильтры + таблица 9 колонок)
      5.3 ✅ PASSED — pages/matching.py (4 раунда; action panel + Plotly radar/donut)
Gate 6   [⬜ TODO]   Dashboard pages — Данные + Аналитика (3 стр)
Gate 7   [⬜ TODO]   Dashboard pages — Система (3 стр)
      — Deferred: Telegram preview в action panel (интеграция с реальным Bot API)
      — Deferred: i18n шаблонов уведомлений (участвовать/пропустить/запросить)
      — Deferred: при изменении формулы calculate_relevance в src/splink_config.py
        синхронно обновить _decompose_relevance в dashboard/pages/matching.py
        и caption-форматы в легенде блока 4 (формулы '× 40%' и т.д.)
Gate 8   [⬜ TODO]   Integration: LLM-judge + Telegram alerts
      — Deferred: реальная отправка уведомлений из action panel → Telegram
      — Deferred: колонка «Спрос» в Каталоге SKU — кол-во тендеров на позицию
        за последние 30 дней. Требует: ежедневный запуск пайплайна (TenderGuru),
        хранение per-SKU попаданий в pipeline_runs.log, агрегация по дате.
        До Gate 8 показывать бессмысленно — данные только из seed-батча (14 тендеров).
Gate 9   [⬜ TODO]   Splink switchover + threshold recalibration
      — Deferred: radar axes из реального Splink feature importance (сейчас mock)
```

**Следующее действие:** Gate 6 — `dashboard/pages/` Данные (Каталог SKU, Win/Loss) + Аналитика (Drill Down).

---

## Правила работы агента

1. **Читай этот файл первым** — до любого кода, до любого grep.
2. **Читай SKILL.md** перед любой работой с дашбордом:
   `.claude/skills/streamlit-design-patterns/SKILL.md`
3. **Читай RULES.md** перед изменением matching-логики: `docs/RULES.md`
4. **Читай DECISIONS.md** перед архитектурными решениями: `docs/DECISIONS.md`
5. **После каждого gate** — обновляй статус в этом файле.
6. **Не начинай Gate N+1** пока не пройден Gate N.
7. **Тесты запускать через** `python -m pytest tests/ -v` — не `pytest tests/`.
   Без `-m` импорты `from src.` падают (нет `conftest.py`, это норма).

---

## Deferred items (memos for future gates)

Решения, принятые в текущих гейтах, но отложенные до конкретного будущего гейта. 
Перед стартом каждого гейта — пройтись по своему списку.

### К Gate 8 (TenderGuru integration)

1. **Страница Обзор → KPI**: добавить дельты для метрик «Активных тендеров», 
   «Срочные», «Сумма НМЦ» — после подключения TenderGuru появится исторический 
   контекст для сравнения «вчера/неделя».

2. **Страница Обзор → график 3**: заменить «Тендеры по регионам» на «Площадки — 
   источники» (или сделать двухуровневый «Регион + Площадка»). До Gate 8 поле 
   платформы в данных отсутствует.

3. **Страница Обзор → фильтры**: добавить единый временной фильтр для всей 
   страницы (1 день / 5 дней / 14 дней / 1 месяц / 3 месяца / 6 месяцев / год) 
   вместо/дополнительно к локальным фильтрам графиков.

4. **Страница Обзор → подзаголовок**: «Сводка по последнему прогону пайплайна» 
   → «Ежедневная сводка по тендерам и матчингу».

### К Gate 9 (Splink switchover + recalibration)

5. **Страница Обзор → блок Аналитика**: добавить text footer под каждым 
   графиком — автогенерируемая подпись с интерпретацией данных (главный лидер, 
   % от общего, сравнение с прошлым периодом). Делать только когда есть 
   достаточно данных и историческая база для сравнений.

---

## Verified Project State (аудит 2026-04-30, финальный)

### Реальные факты — не предположения

| Параметр | Значение |
|----------|----------|
| Pipeline runtime | ~0.7 сек (fallback, Splink не установлен) |
| Pipeline accuracy | **9/14 = 64.3%** |
| Тесты | **293 passed, 1 xfailed** |
| xfail | **только** `IRF740PBF` без дефиса |
| `dashboard/` | папки существуют, **0 Python файлов** |
| `.streamlit/config.toml` | ✅ существует (dark, #FF9800) — не трогать |
| `tests/conftest.py` | ❌ нет — всегда `python -m pytest` |
| `data/last_run.json` | ❌ нет — создаётся в Gate 4 |
| `docs/pipeline_runs.log` | ❌ нет — создаётся в Gate 4 |
| streamlit | ✅ 1.55.0 |
| altair | ✅ 6.0.0 ⚠️ (API отличается от 5.x) |
| pandas | ✅ 2.3.0+ |
| splink | ❌ не установлен (намеренно — переключение в Gate 9) |
| duckdb | ❌ не установлен (намеренно — переключение в Gate 9) |

### ⚠️ Altair 6.x
Установлен altair **6.0.0**. SKILL.md написан под 5.x API.
Синтаксис в основном совместим, но есть отличия.
**Действие:** в начале Gate 5 агент обязан проверить совместимость
первого chart с altair 6.x перед написанием остальных.

### Статус известных багов (верифицировано 2026-04-30)

| Баг | Статус | Как исправлен / план |
|-----|--------|---------------------|
| `светодиод` → ложно как `diode` | ✅ **ИСПРАВЛЕН** | `_keyword_matches()` |
| `мкГн` → ложно как `microcontroller` | ✅ **ИСПРАВЛЕН** | `_keyword_matches()` |
| T-A07: PN extractor → `ETHERNET-IP` вместо `1734-AENT` | ⏳ Gate 3.5 | Добавить в `_STOPWORDS`: `ETHERNET`, `ETHERNETIP`, `ETHERNET-IP` |
| `IRF740PBF` без дефиса не стрипается | ⏳ xfail | Не критично, отдельной задачей |

**`_keyword_matches()` — что делает:**
Функция в `src/domain_dict_electronics.py:358-365` использует
negative lookbehind/lookahead для word boundaries в кириллице и латинице:
```python
def _keyword_matches(keyword: str, text_lower: str) -> bool:
    escaped = re.escape(keyword)
    pattern = r'(?<![a-zа-яё0-9])' + escaped + r'(?![a-zа-яё0-9])'
    return bool(re.search(pattern, text_lower))
```
Это системное решение (не хак) — `detect_category()` вызывает её
для каждого keyword, устраняя все substring collisions разом.
**Не трогать без тестов.**

### Commit history
```
540b845 Phase 1: project structure, CLAUDE.md, SKILL.md, 284 tests, 3 bugs fixed
c8f88fc Initial commit
```
> Примечание: commit message "3 bugs fixed" некорректен.
> По факту исправлено 2 бага. T-A07 и `IRF740PBF` остались.

### Правильные матчи pipeline (8/14, станет 9/14 после Gate 3.5)
T-A01, T-A02, T-A03, T-A04, T-A05, T-A06, T-A08, T-A09 (+ T-A07 после фикса)

### Пропущенные матчи — причины известны
| Тендер | Причина | Когда чинится |
|--------|---------|---------------|
| T-A07 | PN extractor извлекает "ETHERNET-IP" вместо "1734-AENT" | **Gate 3.5** |
| T-B01, T-B02, T-B03 | Сценарий B: fallback не матчит без PN | Gate 9 (Splink) |
| T-C01, T-C02 | Сценарий C: fallback не матчит без PN | Gate 9 (Splink) |

---

## Gate 1 — Core Pipeline ✅ PASSED

| Файл | Статус |
|------|--------|
| `src/__init__.py` | ✅ |
| `src/domain_dict_electronics.py` | ✅ 17 категорий, 200+ aliases, `_keyword_matches()` |
| `src/normalizer_electronics.py` | ✅ ElectronicsRecord, router A/B/C |
| `src/seed_catalog_radal.py` | ✅ 15 позиций |
| `src/test_tenders.py` | ✅ 14 тендеров |
| `src/splink_config.py` | ✅ fallback + relevance |
| `src/demo_pipeline.py` | ✅ end-to-end + VALIDATION |

---

## Gate 2 — Test Suite ✅ PASSED

```bash
python -m pytest tests/ -v
# 284 passed, 1 xfailed — verified 2026-04-30
```

| Файл | Статус |
|------|--------|
| `tests/test_normalizer_pn_edge_cases.py` | ✅ |
| `tests/test_domain_dict.py` | ✅ |
| `tests/test_splink_config.py` | ✅ |

**Coverage gaps — закрываются в Gate 3.5:**
- ~~HIGH: нет теста для T-A07 PN bug (1734-AENT / ETHERNET-IP)~~ → Gate 3.5
- ~~MEDIUM: нет интеграционного теста `demo_pipeline.py`~~ → Gate 3.5

---

## Gate 3 — Matching Engine ✅ PASSED

Пороги верифицированы тестами:
- `classify_match(0.75)` → `"borderline"` ✅
- `classify_match(0.92)` → `"auto"` ✅
- `classify_match(0.749)` → `"reject"` ✅
- `classify_match(0.919)` → `"borderline"` ✅

---

## Gate 3.5 — E2E Product Invariants + T-A07 fix ⏳ NEXT

**Цель.** Зафиксировать архитектурный контракт пайплайна тремя
поведенческими тестами (инвариантами) и закрыть HIGH/MEDIUM coverage gaps.
Эти тесты защищают продукт во всех последующих Gates, особенно при
подключении LLM-judge (Gate 8) и переключении на Splink (Gate 9).

**Почему именно здесь, а не в Gate 9.** Инварианты должны существовать
**до** изменений, которые они страхуют. Gates 4–8 будут активно трогать
структуру результатов пайплайна (кэш, дашборд, LLM-интеграция). Без
E2E-тестов любая регрессия в matching будет замечена только в Gate 9 —
слишком поздно. T-A07 fix добавлен сюда же: трогаем нормализатор и
тесты — имеет смысл за один заход поднять accuracy с 8/14 до 9/14.

### Порядок выполнения (строго последовательно)

```
3.5.0 → T-A07 fix (стоп-лист + юнит-тест)
3.5.1 → Рефакторинг demo_pipeline.py (run_pipeline → dict)
3.5.2 → tests/test_pipeline_e2e.py (3 инварианта)
3.5.3 → docs/RULES.md §7 (фиксация инвариантов)
3.5.4 → Проверка критериев прохождения
```

---

### Шаг 3.5.0 — T-A07 fix

**Проблема.** Тендер T-A07 содержит «Allen-Bradley POINT I/O EtherNet/IP
Adapter 1734-AENT». Текущий PN extractor извлекает `ETHERNET-IP` как
candidate part number и берёт его первым, вместо реального PN `1734-AENT`.

**Фикс.** В `src/normalizer_electronics.py` функция `_extract_part_numbers`,
расширить `_STOPWORDS`:

```python
_STOPWORDS = {
    "SIEMENS", "SIMATIC", "MITSUBISHI", "ELECTRIC", "XILINX", "ALTERA",
    "OMRON", "SEMIKRON", "INFINEON", "VISHAY", "MICROCHIP", "MICROSEMI",
    "FUJI", "POWERFLEX", "ALLEN-BRADLEY", "ROCKWELL", "HITACHI",
    "KINGBRIGHT", "QORVO", "CYPRESS", "MAXIM", "ATMEL", "KEMET",
    "IGBT", "MOSFET", "FPGA", "CPLD", "PLIS",
    # T-A07 fix: industrial protocols, not part numbers
    "ETHERNET", "ETHERNETIP", "ETHERNET-IP",
    "PROFINET", "PROFIBUS", "MODBUS", "DEVICENET", "CANOPEN",
}
```

Помимо `ETHERNET-IP` добавлены ещё несколько частых протоколов
промавтоматики — превентивно для аналогичных случаев в реальных
тендерах (Profinet, Modbus и т.п.).

**Тест.** Новый файл `tests/test_normalizer_t_a07.py`:

```python
"""Регрессионный тест на T-A07 (Allen-Bradley 1734-AENT)."""
from src.normalizer_electronics import normalize_tender_item


def test_normalizer_pn_allen_bradley_1734_aent():
    """T-A07: PN '1734-AENT' извлекается, 'ETHERNET-IP' игнорируется."""
    rec = normalize_tender_item(
        source_id="T-A07-test",
        name="Allen-Bradley POINT I/O EtherNet/IP Adapter 1734-AENT",
    )
    assert "1734-AENT" in rec.part_numbers
    assert "ETHERNET-IP" not in rec.part_numbers
    assert "ETHERNETIP" not in rec.part_numbers
    assert rec.part_number_primary == "1734-AENT"


def test_normalizer_pn_industrial_protocols_excluded():
    """Промышленные протоколы не должны попадать в part_numbers."""
    for protocol in ["PROFINET", "MODBUS", "DEVICENET"]:
        rec = normalize_tender_item(
            source_id="protocol-test",
            name=f"Адаптер {protocol} для шасси AB-5000",
        )
        assert protocol not in rec.part_numbers, f"{protocol} попал в PN"
```

**Проверка.**
```bash
python -m pytest tests/test_normalizer_t_a07.py -v
# → 2 passed
python -m src.demo_pipeline 2>&1 | grep "T-A07"
# → строка с T-A07 показывает PN: 1734-AENT (не ETHERNET-IP)
```

---

### Шаг 3.5.1 — Рефакторинг `demo_pipeline.py`

**Цель.** Вынести чистую функцию `run_pipeline() -> dict`, чтобы тесты
могли вызывать её в памяти без subprocess и без парсинга stdout.

**Структура файла после рефакторинга:**

```
demo_pipeline.py
├── run_pipeline() -> dict        # вся логика, возвращает structured result
├── _format_nmc()                 # как было, helper
├── _print_report(result: dict)   # вся печать в stdout
├── main()                        # тонкая обёртка
```

**Что возвращает `run_pipeline()`:**

```python
{
    "timestamp": "2026-04-30T15:42:01",
    "catalog": [...],            # raw catalog list
    "tenders": [...],            # raw tenders list
    "results": [...],            # все matching pairs
    "best_matches": {            # tender_id → (catalog_id, probability)
        "T-A01": ("RAD-001", 0.96),
        ...
    },
    "validation": {
        "correct": 9,            # после Gate 3.5
        "missed": 5,
        "total": 14,
        "details": [
            {"tender_id": "T-A01", "expected": "RAD-001",
             "actual": "RAD-001", "score": 0.96, "ok": True},
            ...
        ],
    },
    "summary": {
        "auto": int,
        "borderline": int,
        "reject": int,
    },
}
```

**Критично не сломать:**
- Stdout-вывод должен остаться **посимвольно тем же** — пользователи
  привыкли к формату, и в Gate 4 он будет сравниваться с pipeline_runs.log.
- Gate 4 кэш (`data/last_run.json`) пишется из той же `run_pipeline()`,
  чтобы не было drift между тем, что в кэше, и тем, что напечатано.

**Проверка после рефакторинга.**
```bash
# Вывод stdout идентичен предыдущему запуску
python -m src.demo_pipeline > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt
# → пусто

# run_pipeline возвращает структуру
python -c "
from src.demo_pipeline import run_pipeline
r = run_pipeline()
assert 'results' in r and 'best_matches' in r and 'validation' in r
print('OK:', r['validation']['correct'], '/', r['validation']['total'])
"
# → OK: 9 / 14
```

---

### Шаг 3.5.2 — `tests/test_pipeline_e2e.py`

**Module docstring** (первое, что увидит читающий файл):

```python
"""
test_pipeline_e2e.py — Архитектурные инварианты пайплайна.

Эти три теста — НЕ юниты. Они проверяют поведенческие контракты
продукта, которые должны выполняться при любом движке matching
(fallback, Splink, будущие версии).

Инварианты:
  1. Happy path: тендер с точным PN, который есть в каталоге,
     попадает в auto-decision.
  2. Garbage rejection: тендер без связи с каталогом не попадает
     в auto ни при каком движке.
  3. Parametric isolation: тендер сценария B (без PN) не попадает
     в auto — обязан пройти LLM-judge через borderline.

Запрещено привязывать к точным probability/счёту матчей —
тесты должны выдержать смену движка без правок. См. RULES.md §7.
"""
```

**Три теста (каркас, не финальный код):**

```python
import pytest
from src.demo_pipeline import run_pipeline


@pytest.fixture(scope="module")
def pipeline_result():
    """Прогон пайплайна один раз на весь модуль."""
    return run_pipeline()


def test_happy_path_exact_pn_routes_to_auto(pipeline_result):
    """T-A01 (CM1000E3U-34NF Mitsubishi) → RAD-001 в auto."""
    auto_pairs = [
        r for r in pipeline_result["results"]
        if r["tender_id"] == "T-A01"
        and r["catalog_id"] == "RAD-001"
        and r["decision"] == "auto"
    ]
    assert len(auto_pairs) == 1, (
        "Контракт продукта: тендер с точным PN, который есть в каталоге, "
        "обязан попасть в auto-decision без LLM-вмешательства."
    )


def test_garbage_tender_never_routes_to_auto():
    """Синтетический мусор не должен матчиться в auto ни с одним SKU."""
    from src.normalizer_electronics import normalize_tender_item
    from src.splink_config import (
        prepare_catalog_for_splink,
        prepare_tenders_for_splink,
        run_matching_pipeline,
    )
    from src.seed_catalog_radal import get_seed_catalog

    # Полностью несвязанный с электроникой тендер
    garbage = [{
        "id": "T-GARBAGE",
        "name": "Поставка офисной бумаги формата А4 80 г/м² 500 листов",
        "okpd2": "17.23",
        "region": "Москва",
        "price_max": 50_000.0,
        "quantity_str": "100 уп",
        "deadline_days": 30,
    }]

    catalog = prepare_catalog_for_splink(get_seed_catalog())
    tenders = prepare_tenders_for_splink(garbage)
    results = run_matching_pipeline(catalog, tenders)

    auto_matches = [r for r in results if r["decision"] == "auto"]
    assert len(auto_matches) == 0, (
        f"Контракт продукта: precision > recall. Мусорный тендер не должен "
        f"генерировать auto-алерты. Найдено {len(auto_matches)} ложных auto-матчей."
    )


def test_parametric_match_never_routes_to_auto(pipeline_result):
    """T-B01 (сценарий B: параметры без PN) не должен попасть в auto."""
    b01_pairs = [
        r for r in pipeline_result["results"] if r["tender_id"] == "T-B01"
    ]
    auto_pairs = [r for r in b01_pairs if r["decision"] == "auto"]

    assert len(auto_pairs) == 0, (
        "Архитектурный контракт: параметрический матч (сценарий B, без PN) "
        "обязан проходить через LLM-judge как borderline. "
        f"Найдено {len(auto_pairs)} нарушений — параметрика ушла в auto без LLM."
    )
```

**Запрещено в этих тестах:**
- Привязка к точным значениям probability (`0.96`, `0.84` — нет).
- Привязка к точному количеству матчей (`assert len(...) == 5` — нет).
- Mock'и нормализатора, splink_config, scenario router (только настоящие вызовы).
- Чтение stdout или `data/last_run.json` (только in-memory dict).

---

### Шаг 3.5.3 — `docs/RULES.md` §7 «Product invariants»

Добавить новый раздел в RULES.md (после §6 Dashboard):

```markdown
## 7. Product invariants (поведенческие, движок-независимые)

Три инварианта, проверяемых `tests/test_pipeline_e2e.py`.
Нарушение любого = баг, независимо от того, какой движок (fallback / Splink) активен.

| # | Инвариант | Тест | Связь с правилами |
|---|-----------|------|-------------------|
| 1 | Тендер с точным PN из каталога → auto-decision | test_happy_path_exact_pn_routes_to_auto | §1 (PN — главный ключ) |
| 2 | Тендер без связи с каталогом → не auto | test_garbage_tender_never_routes_to_auto | §2 (precision > recall) |
| 3 | Параметрический матч (сценарий B) → не auto | test_parametric_match_never_routes_to_auto | §1, §3 (LLM только для borderline) |

Эти инварианты не зависят от:
- Текущей probability на fallback-скоринге
- Установлен ли Splink
- Конкретных весов в `splink_config.py`
- Точного количества матчей в результатах

При смене движка тесты не переписываются. Если они краснеют после
смены — либо нарушен контракт продукта (правим продакшн-код),
либо тест был написан как «факт», а не «инвариант» (правим тест).
```

---

### Критерий прохождения Gate 3.5

```bash
# 1. T-A07 fix
python -m pytest tests/test_normalizer_t_a07.py -v
# → 2 passed

# 2. E2E инварианты
python -m pytest tests/test_pipeline_e2e.py -v
# → 3 passed

# 3. Полный набор тестов
python -m pytest tests/ -v --tb=short
# → 287+ passed, 1 xfailed (284 + 2 на T-A07 + 3 на E2E)

# 4. Pipeline с улучшенной accuracy
python -m src.demo_pipeline
# → "Accuracy: 9/14 = 64.3%" в выводе валидации
# → exit code 0

# 5. run_pipeline() возвращает корректную структуру
python -c "
from src.demo_pipeline import run_pipeline
r = run_pipeline()
assert r['validation']['correct'] == 9
assert all(k in r for k in ['catalog', 'tenders', 'results', 'best_matches', 'summary'])
print('OK: structure valid, accuracy', r['validation']['correct'], '/', r['validation']['total'])
"

# 6. Stdout не сломан
python -m src.demo_pipeline > /tmp/after.txt 2>&1
# → формат вывода совпадает с предыдущей версией (визуальная проверка)
```

### После Gate 3.5: что обновить в этом файле

- Статус Gate 3.5: `⏳ NEXT` → `✅ PASSED`
- Статус Gate 4: `⬜ TODO` → `⏳ NEXT`
- Verified Project State: accuracy `8/14` → `9/14`, тестов `284` → `289`
- Список «правильных матчей»: добавить T-A07
- Таблица «Пропущенные»: убрать T-A07
- Таблица «Известные баги»: T-A07 → ✅ ИСПРАВЛЕН

---

## Gate 4 — Pipeline Cache + Dashboard Foundation ⬜ TODO

> Зависит от Gate 3.5 — `run_pipeline()` уже возвращает dict, который
> ровно в этой форме записывается в `data/last_run.json`.

### Порядок выполнения (строго последовательно)

```
4.0 → Pipeline cache (data/last_run.json + docs/pipeline_runs.log)
4.1 → dashboard/chart_utils.py
4.2 → dashboard/data_utils.py
4.3 → dashboard/streamlit_app.py
4.4 → dashboard/pages/ заглушки (9 файлов)
4.5 → Проверка критериев прохождения
```

---

### Шаг 4.0 — Pipeline Cache

**Зависимость от Gate 3.5.** В Gate 3.5 уже создана `run_pipeline() -> dict`.
Здесь только добавляем запись результата в файл:

```python
# в main() в src/demo_pipeline.py
import json
from pathlib import Path

def main():
    result = run_pipeline()
    _print_report(result)

    # Кэш для дашборда
    Path("data").mkdir(exist_ok=True)
    Path("data/last_run.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str)
    )

    # Лог запусков
    Path("docs").mkdir(exist_ok=True)
    with open("docs/pipeline_runs.log", "a", encoding="utf-8") as f:
        v = result["validation"]
        f.write(
            f"{result['timestamp']} | "
            f"accuracy={v['correct']}/{v['total']} | "
            f"matches={len(result['results'])} | "
            f"runtime=fallback\n"
        )
```

**Проверка:**
```bash
python -m src.demo_pipeline
test -f data/last_run.json      && echo "OK: cache exists"
test -f docs/pipeline_runs.log  && echo "OK: log exists"
python -m pytest tests/test_pipeline_e2e.py -v
# → 3 passed (E2E не должны сломаться от добавления кэша)
```

---

### Шаг 4.1 — `dashboard/chart_utils.py`

```python
"""chart_utils.py — единый источник цветов и Altair-настроек.
Никогда не хардкодить hex-цвета в page-файлах — только импортировать отсюда.
"""
from __future__ import annotations
import altair as alt

# ── UI ──────────────────────────────────────────
PRIMARY_COLOR    = '#FF9800'

# ── Match decisions ─────────────────────────────
COLOR_AUTO       = '#16a34a'
COLOR_BORDERLINE = '#FACC15'
COLOR_REJECT     = '#EF4444'
COLOR_NEUTRAL    = '#6B7280'

# ── Scenarios ───────────────────────────────────
COLOR_SCENARIO_A = '#3B82F6'
COLOR_SCENARIO_B = '#8B5CF6'
COLOR_SCENARIO_C = '#6B7280'

# ── Semantic aliases ────────────────────────────
COLOR_GOOD    = COLOR_AUTO
COLOR_WARNING = COLOR_BORDERLINE
COLOR_DANGER  = COLOR_REJECT
COLOR_MUTED   = COLOR_NEUTRAL

# ── Palettes ────────────────────────────────────
RAINBOW_PALETTE = ['#8B5CF6', '#3B82F6', '#10B981', '#FACC15', '#F59E0B', '#EF4444']
COMPARE_PALETTE = ['#8B5CF6', '#F59E0B']

# ── Sort orders ─────────────────────────────────
DECISION_ORDER = ["auto", "borderline", "reject"]
SCENARIO_ORDER = ["A", "B", "C"]

# ── Altair scales (altair 6.x) ──────────────────
DECISION_SCALE = alt.Scale(
    domain=DECISION_ORDER,
    range=[COLOR_AUTO, COLOR_BORDERLINE, COLOR_REJECT],
)
SCENARIO_SCALE = alt.Scale(
    domain=SCENARIO_ORDER,
    range=[COLOR_SCENARIO_A, COLOR_SCENARIO_B, COLOR_SCENARIO_C],
)
```

---

### Шаг 4.2 — `dashboard/data_utils.py`

```python
"""data_utils.py — загрузка данных для дашборда.
Читает data/last_run.json. Если файл отсутствует — запускает pipeline один раз.
Никогда не читать JSON напрямую в page-файлах — только через функции отсюда.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
import pandas as pd
import streamlit as st

CACHE_PATH = Path("data/last_run.json")


def _ensure_cache() -> None:
    """Если кэша нет — запускаем pipeline один раз."""
    if not CACHE_PATH.exists():
        subprocess.run(["python", "-m", "src.demo_pipeline"], check=True)


@st.cache_data
def load_pipeline_results() -> pd.DataFrame:
    """Результаты matching из последнего запуска pipeline."""
    _ensure_cache()
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return pd.DataFrame(data["results"])


@st.cache_data
def load_catalog() -> pd.DataFrame:
    """Seed-каталог Radal (15 позиций)."""
    _ensure_cache()
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return pd.DataFrame(data["catalog"])


@st.cache_data
def load_tenders() -> pd.DataFrame:
    """Тендеры с результатами matching (best_match добавляется здесь)."""
    _ensure_cache()
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    tenders_df = pd.DataFrame(data["tenders"])
    bm = data["best_matches"]
    tenders_df["best_match_id"] = tenders_df["id"].map(
        lambda tid: bm.get(tid, [None, 0])[0]
    )
    tenders_df["best_match_score"] = tenders_df["id"].map(
        lambda tid: bm.get(tid, [None, 0])[1]
    )
    return tenders_df


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Агрегированные метрики для страницы Обзор."""
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
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    v = data.get("validation", {})
    return {
        "timestamp": data.get("timestamp", "—"),
        "accuracy":  f"{v.get('correct', 0)}/{v.get('total', 0)}",
    }
```

---

### Шаг 4.3 — `dashboard/streamlit_app.py`

```python
"""streamlit_app.py — точка входа. Только навигация, никакого контента."""
from __future__ import annotations
import streamlit as st

# ПЕРВЫЙ вызов — до всего остального
st.set_page_config(
    page_title="GoldenMatch Pro",
    page_icon=":material/precision_manufacturing:",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

with st.sidebar:
    st.divider()
    with st.container(border=True):
        st.caption("Подключения")
        st.markdown(":material/error: TenderGuru — не настроен")
        st.markdown(":material/error: B2B-Center — не настроен")
        st.markdown(":material/error: Splink — не установлен")

pg.run()
```

---

### Шаг 4.4 — `dashboard/pages/` заглушки (9 файлов)

Каждый файл — минимум, не крашится, заменяется в Gates 5-7:

```python
# overview.py
import streamlit as st
st.markdown("#### :primary[:material/dashboard:] Обзор")
st.info("Страница в разработке — Gate 5")
```

(Аналогично для tender_feed, matching → Gate 5; catalog, win_loss, drill_down → Gate 6; settings, connections, faq → Gate 7.)

---

### Критерий прохождения Gate 4

```bash
# 1. Pipeline cache
python -m src.demo_pipeline
test -f data/last_run.json     && echo "OK: cache exists"
test -f docs/pipeline_runs.log && echo "OK: log exists"

# 2. data_utils работает автономно
python -c "
import sys; sys.path.insert(0, '.')
from dashboard.data_utils import load_pipeline_results, load_catalog, load_tenders
print('Results:', len(load_pipeline_results()), 'rows')
print('Catalog:', len(load_catalog()), 'rows')
print('Tenders:', len(load_tenders()), 'rows')
"
# → Results: >0 rows
# → Catalog: 15 rows
# → Tenders: 14 rows

# 3. Dashboard запускается
python -m streamlit run dashboard/streamlit_app.py
# → Нет ошибок импорта
# → 9 пунктов навигации в 4 группах
# → Статус подключений в sidebar

# 4. E2E инварианты не сломаны
python -m pytest tests/test_pipeline_e2e.py -v
# → 3 passed

# 5. Полный набор тестов
python -m pytest tests/ -v --tb=short
# → 289 passed, 1 xfailed (без изменений после Gate 3.5)
```

### Запрещено в Gate 4 (из SKILL.md)
- Хардкодить hex-цвета вне `chart_utils.py`
- Фильтры в sidebar
- Контент страниц в `streamlit_app.py`
- Emoji-маркеры (✅⚠️❌) для статусов
- `unsafe_allow_html=True`
- matplotlib или plotly — только Altair
- Читать JSON напрямую в pages — только через data_utils

---

## Gate 5 — Dashboard Pages: Мониторинг ⬜ TODO

**Читать перед началом:**
1. `.claude/skills/streamlit-design-patterns/SKILL.md`
2. Проверить совместимость первого chart с **altair 6.x** перед написанием остальных

### Страницы
| Файл | Приоритет |
|------|-----------|
| `pages/overview.py` | HIGH |
| `pages/tender_feed.py` | HIGH |
| `pages/matching.py` | HIGH |

### `overview.py`
- 4 метрики: всего тендеров / auto / borderline / accuracy
- Bar chart: decisions (DECISION_SCALE из chart_utils)
- Bar chart: сценарии A/B/C (SCENARIO_SCALE из chart_utils)
- Bar chart: топ категорий (RAINBOW_PALETTE)
- Insights panel [3:1]: вычисленные из данных, не хардкод

### `tender_feed.py`
- Фильтры в main area: decision, scenario, region
- `st.dataframe` с column_config:
  - `match_probability` → `ProgressColumn`
  - `decision` → `TextColumn` (без emoji)
- `st.session_state["selected_tender_id"]` при выборе строки

### `matching.py`
- Selectbox или session_state из tender_feed
- Decision: `st.success/warning/error` (не emoji, не хардкод цвет)
- Relevance breakdown: bar chart (4 компонента)

### Критерий прохождения Gate 5
```bash
python -m streamlit run dashboard/streamlit_app.py
# Все 3 страницы открываются без ошибок
# Нет хардкода hex в page-файлах
# Нет emoji-маркеров для статусов
# Данные из data_utils, не хардкод
# Altair charts рендерятся корректно (6.x)
```

---

## Gate 6 — Dashboard Pages: Данные + Аналитика ⬜ TODO

| Файл | Содержание |
|------|-----------|
| `pages/catalog.py` | Таблица 15 SKU, фильтры category/MFR/in_stock |
| `pages/win_loss.py` | Заглушка с инструкцией по подключению TenderGuru |
| `pages/drill_down.py` | Redirect на win_loss если нет session_state |

---

## Gate 7 — Dashboard Pages: Система ⬜ TODO

| Файл | Содержание |
|------|-----------|
| `pages/settings.py` | Пороги 0.75/0.92 — display only (MVP) |
| `pages/connections.py` | Статус TenderGuru/B2B-Center/Splink + инструкции |
| `pages/faq.py` | Сценарии A/B/C, пороги, relevance formula |

---

## Gate 8 — Integration: LLM-judge + Telegram ⬜ TODO

### Файлы
```
src/llm_judge.py        # GigaChat/YandexGPT + fallback → manual queue
src/telegram_alerts.py  # Telegram Bot API
```

### Правила (RULES.md §3) — нарушение = баг
- LLM только для borderline (0.75–0.92)
- НИКОГДА для auto/reject
- Таймаут 5 сек → `{"decision": "manual", "reason": "timeout"}`
- Pipeline никогда не ломается из-за LLM

### Защита E2E-инвариантами
Тест 3 (`test_parametric_match_never_routes_to_auto`) **обязан** оставаться
зелёным после интеграции LLM. Если LLM-judge начнёт повышать decision
с borderline на auto в обход порогов — тест упадёт. Это намеренная
защита: LLM может только подтвердить или отклонить borderline, не
повысить уверенность сверх архитектурного порога.

### Критерий прохождения Gate 8
```bash
python -m pytest tests/test_pipeline_e2e.py -v
# → 3 passed (инварианты не нарушены LLM-интеграцией)

python -m pytest tests/ -v
# → 289+ passed
```

---

## Gate 9 — Splink Switchover + Threshold Recalibration ⬜ TODO

> **Что изменилось vs v1 плана:** из этого Gate удалён фикс T-A07 — он
> переехал в Gate 3.5. Здесь остаётся только то, что требует всей
> предыдущей инфраструктуры: безопасное переключение движка matching.

### Почему Splink именно в финале

**Аргументы за поздний переход (а не раньше):**

1. **Splink — это другая модель скоринга, не «бэкенд побыстрее».**
   EM-алгоритм автоматически калибрует веса PN/MFR/category на реальных
   данных. Probabilities сдвинутся, распределение auto/borderline/reject
   полностью пересчитается, пороги 0.92/0.75 потребуют перекалибровки.

2. **На 14 тендерах × 15 SKU = 210 пар Splink не обучится осмысленно.**
   EM требует достаточного объёма для оценки u-вероятностей. На seed-данных
   веса будут шумными и нестабильными между запусками. Реальная калибровка
   нужна **после** подключения TenderGuru, когда у вас тысячи тендеров.

3. **Дашборд проектируется под структуру результатов, не под их значения.**
   Gate 5 рисует страницы на тех данных, которые есть. Если accuracy
   9/14 → 11/14 после Splink — структура `results` не меняется,
   страницы рисовать одинаково. Splink не разблокирует дашборд.

4. **К Gate 9 собрана вся защитная инфраструктура.**
   E2E-инварианты (Gate 3.5), кэш для сравнения (Gate 4), визуальная
   валидация распределений (Gates 5–7), лог запусков (Gate 4),
   LLM-fallback (Gate 8). Переключение движка обкладывается всеми
   safety nets — это правильное место для рискованного изменения.

### Порядок действий

```
9.0 → Snapshot до переключения (бэкап data/last_run.json)
9.1 → pip install splink duckdb
9.2 → python -m src.demo_pipeline (Splink path активируется)
9.3 → pytest tests/test_pipeline_e2e.py — safety check
9.4 → Сравнение распределений до/после
9.5 → Перекалибровка порогов (если требуется)
9.6 → Финальная валидация
```

---

### Шаг 9.0 — Snapshot

```bash
cp data/last_run.json data/last_run_fallback.json
echo "$(date +%Y-%m-%d) | fallback baseline | $(python -c 'import json; d=json.load(open(\"data/last_run.json\")); print(f\"acc={d[\"validation\"][\"correct\"]}/{d[\"validation\"][\"total\"]}, auto={d[\"summary\"][\"auto\"]}, bl={d[\"summary\"][\"borderline\"]}\")')" >> docs/pipeline_runs.log
```

### Шаг 9.1 — Установка

```bash
pip install splink>=4.0.0 duckdb>=0.9.0
python -c "import splink; print('splink OK:', splink.__version__)"
```

### Шаг 9.2 — Запуск пайплайна на Splink

```bash
python -m src.demo_pipeline
# → ветка _run_with_splink() активна (без сообщения "Splink не установлен")
# → результаты записаны в data/last_run.json
```

### Шаг 9.3 — Safety check инвариантами

```bash
python -m pytest tests/test_pipeline_e2e.py -v
```

**Что значит результат:**
- **3 passed** → архитектурный контракт сохранён, можно идти дальше.
- **Test 1 failed** (happy path) → Splink не находит exact PN match.
  Скорее всего, проблема в blocking rules или весах. Не идти дальше,
  чинить до прохождения.
- **Test 2 failed** (garbage в auto) → Splink даёт ложные auto-матчи.
  Серьёзно. Поднять порог auto **до** деплоя (RULES.md §2: precision > recall).
- **Test 3 failed** (параметрика в auto) → Splink даёт >0.92 для матчей
  без PN. Архитектурное нарушение. Либо повысить порог, либо подкрутить
  веса (PN exact должен иметь больший вес).

### Шаг 9.4 — Сравнение распределений

```python
# scripts/compare_distributions.py
import json

before = json.load(open("data/last_run_fallback.json"))
after  = json.load(open("data/last_run.json"))

print("Metric           Fallback   Splink    Δ")
print("Accuracy         {}/{}     {}/{}    {}".format(
    before["validation"]["correct"], before["validation"]["total"],
    after["validation"]["correct"],  after["validation"]["total"],
    after["validation"]["correct"] - before["validation"]["correct"],
))
print("Auto             {:<10} {:<9} {:+}".format(
    before["summary"]["auto"], after["summary"]["auto"],
    after["summary"]["auto"] - before["summary"]["auto"],
))
print("Borderline       {:<10} {:<9} {:+}".format(
    before["summary"]["borderline"], after["summary"]["borderline"],
    after["summary"]["borderline"] - before["summary"]["borderline"],
))
```

### Шаг 9.5 — Перекалибровка порогов (если нужно)

Только если Шаг 9.3 показал нарушение инвариантов или Шаг 9.4 показал
серьёзный сдвиг распределений (например, >50% всех пар в auto). Менять
константы в `splink_config.py`:
- `THRESHOLD_AUTO_MATCH` (текущее значение 0.92)
- `THRESHOLD_BORDERLINE_LOW` (текущее значение 0.75)

После каждого изменения — повторить `pytest tests/test_pipeline_e2e.py`.

### Шаг 9.6 — Финальная валидация

```bash
# 1. Все тесты
python -m pytest tests/ -v
# → 289+ passed, 1 xfailed (IRF740PBF — не критично)

# 2. Pipeline accuracy на Splink
python -m src.demo_pipeline
# → Accuracy ≥ 11/14 (улучшение vs fallback 9/14 за счёт сценариев B/C)

# 3. Dashboard работает на Splink-данных
python -m streamlit run dashboard/streamlit_app.py
# → Все 9 страниц открываются
# → Цифры в Обзоре отражают новое распределение

# 4. Coverage
/check-coverage
# → Нет HIGH gaps
```

---

## Команды агента

```bash
# Тесты — ВСЕГДА через python -m
python -m pytest tests/ -v --tb=short

# E2E инварианты отдельно (быстрая проверка контракта)
python -m pytest tests/test_pipeline_e2e.py -v

# Pipeline
python -m src.demo_pipeline

# Dashboard
python -m streamlit run dashboard/streamlit_app.py

# Claude Code commands
/run-pipeline        # запуск + сравнение с pipeline_runs.log
/validate-matching   # проверка правил из RULES.md
/check-coverage      # gaps в тестах
```

---

## Структура проекта (целевая)

```
goldenmatch-radal/
├── .claude/
│   ├── agents/
│   │   ├── normalizer-reviewer.md    ✅
│   │   └── test-writer.md            ✅
│   ├── commands/
│   │   ├── check-coverage.md         ✅
│   │   ├── run-pipeline.md           ✅
│   │   └── validate-matching.md      ✅
│   └── skills/streamlit-design-patterns/
│       └── SKILL.md                  ✅ (написан под 5.x, проверить в Gate 5)
├── .streamlit/
│   └── config.toml                   ✅ не трогать
├── data/
│   ├── last_run.json                 ⏳ Gate 4
│   └── last_run_fallback.json        ⏳ Gate 9 (snapshot перед Splink)
├── src/                              ✅ Gates 1-3
│   ├── demo_pipeline.py              ⏳ Gate 3.5: + run_pipeline() -> dict
│   ├── normalizer_electronics.py     ⏳ Gate 3.5: + ETHERNET-IP стоп-слова
│   └── domain_dict_electronics.py    ✅ _keyword_matches() — не трогать без тестов
├── tests/                            ✅ 284 passed, 1 xfailed
│   ├── test_normalizer_t_a07.py      ⏳ Gate 3.5 (NEW)
│   └── test_pipeline_e2e.py          ⏳ Gate 3.5 (NEW)
├── dashboard/                        ⏳ Gates 4-7
│   ├── streamlit_app.py
│   ├── data_utils.py
│   ├── chart_utils.py
│   └── pages/ (9 файлов)
├── docs/
│   ├── DECISIONS.md                  ✅
│   ├── RULES.md                      ⏳ Gate 3.5: + §7 Product invariants
│   ├── architecture_v2.md            ✅
│   └── pipeline_runs.log             ⏳ Gate 4
├── AGENTS.md                         ✅
├── CLAUDE.md                         ✅
├── WORKFLOW.md                       ← этот файл (v2)
├── requirements.txt                  ✅
└── README.md                         ✅
```

---

## Карта инвариантов: что когда защищается

| Gate | Какой риск возникает | Какой инвариант страхует |
|------|---------------------|--------------------------|
| 4 | Кэш ломает структуру `results` | Test 1 (happy path) |
| 4 | `data_utils.py` неверно парсит decision | Test 1, 2 |
| 5 | Dashboard читает поле, которого больше нет | косвенно через Test 1 |
| 8 | LLM-judge поднимает borderline → auto в обход порога | Test 3 |
| 8 | LLM таймаут переводит запрос в auto, а не manual queue | Test 3 |
| 9 | Splink даёт высокую probability мусору | Test 2 |
| 9 | Splink + EM-веса → параметрика в auto без LLM | Test 3 |
| 9 | Splink не находит exact PN match | Test 1 |
