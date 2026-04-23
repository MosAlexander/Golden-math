"""
test_tenders.py — Тестовые тендеры для проверки матчинга с seed-каталогом Radal.

Паттерны взяты из реальных тендеров на электронные компоненты:
  - zakupki.gov.ru (44-ФЗ / 223-ФЗ)
  - rostender.info (категория «электронные компоненты»)
  - B2B-Center

Покрывает все 3 сценария:
  A — точный part number в тексте
  B — параметры без PN
  C — общее описание
"""

TEST_TENDERS = [
    # ════════════════════════════════════════
    # СЦЕНАРИЙ A: точный part number (~70%)
    # ════════════════════════════════════════
    {
        "id": "T-A01",
        "name": "Поставка IGBT-модулей CM1000E3U-34NF производства Mitsubishi "
                "для нужд ООО НПО Центротех",
        "okpd2": "26.11.12",
        "region": "Свердловская область",
        "price_max": 2_800_000.0,
        "quantity_str": "12 шт",
        "deadline_days": 5,
        "expected_match": "RAD-001",
    },
    {
        "id": "T-A02",
        "name": "Закупка модулей ввода Siemens 6ES7321-1BL00-0AA0 "
                "для модернизации АСУТП цеха №3",
        "okpd2": "26.51.43",
        "region": "Московская область",
        "price_max": 450_000.0,
        "quantity_str": "8 шт",
        "deadline_days": 10,
        "expected_match": "RAD-011",
    },
    {
        "id": "T-A03",
        "name": "Поставка ПЛИС XC7A35T-1CPG236C Xilinx Artix-7 "
                "для опытного производства радиоэлектронной аппаратуры",
        "okpd2": "26.11.12",
        "region": "Санкт-Петербург",
        "price_max": 180_000.0,
        "quantity_str": "20 шт",
        "deadline_days": 14,
        "expected_match": "RAD-013",
    },
    {
        "id": "T-A04",
        "name": "Поставка силового модуля IGBT 7MBR75U2B060 Fuji Electric "
                "для частотных преобразователей насосной станции",
        "okpd2": "26.11.12",
        "region": "Краснодарский край",
        "price_max": 960_000.0,
        "quantity_str": "6 шт",
        "deadline_days": 7,
        "expected_match": "RAD-004",
    },
    {
        "id": "T-A05",
        "name": "Закупка блока питания SITOP PSU8200 6EP3436-8SB00-0AY0 "
                "Siemens 24V 20A для шкафа управления",
        "okpd2": "27.11.43",
        "region": "Татарстан",
        "price_max": 120_000.0,
        "quantity_str": "3 шт",
        "deadline_days": 12,
        "expected_match": "RAD-014",
    },
    {
        "id": "T-A06",
        "name": "Поставка драйвера IGBT 1SD536F2-CM1200E4C-34N Concept "
                "для системы управления электроприводом",
        "okpd2": "26.11.12",
        "region": "Челябинская область",
        "price_max": 340_000.0,
        "quantity_str": "5 шт",
        "deadline_days": 8,
        "expected_match": "RAD-009",
    },
    {
        "id": "T-A07",
        "name": "Закупка адаптера EtherNet/IP Allen-Bradley 1734-AENT "
                "для распределённой системы ввода/вывода",
        "okpd2": "26.20.16",
        "region": "Ростовская область",
        "price_max": 85_000.0,
        "quantity_str": "4 шт",
        "deadline_days": 15,
        "expected_match": "RAD-012",
    },

    # Вариации написания PN (тест на нормализацию)
    {
        "id": "T-A08",
        "name": "Поставка модуля IGBT cm1000e3u-34nf (аналог допускается) "
                "для нужд энергетической компании",
        "okpd2": "26.11.12",
        "region": "ХМАО",
        "price_max": 1_500_000.0,
        "quantity_str": "4 шт",
        "deadline_days": 6,
        "expected_match": "RAD-001",  # lowercase PN → must still match
    },
    {
        "id": "T-A09",
        "name": "Поставка модуля ввода 6ES7 321-1BL00-0AA0 Сименс "
                "для АСУТП котельной",
        "okpd2": "26.51.43",
        "region": "Новосибирская область",
        "price_max": 95_000.0,
        "quantity_str": "2 шт",
        "deadline_days": 20,
        "expected_match": "RAD-011",  # space in PN + «Сименс» → must match
    },

    # ════════════════════════════════════════
    # СЦЕНАРИЙ B: параметры без PN (~20%)
    # ════════════════════════════════════════
    {
        "id": "T-B01",
        "name": "Поставка IGBT-модулей 600В 75А для частотных преобразователей "
                "водоочистной станции",
        "okpd2": "26.11.12",
        "region": "Краснодарский край",
        "price_max": 480_000.0,
        "quantity_str": "3 шт",
        "deadline_days": 9,
        "expected_match": "RAD-004",  # 7MBR75U2B060 = 600V 75A
    },
    {
        "id": "T-B02",
        "name": "Закупка тиристорных модулей 600В 55А для электропривода "
                "конвейерной линии",
        "okpd2": "26.11.12",
        "region": "Челябинская область",
        "price_max": 220_000.0,
        "quantity_str": "4 шт",
        "deadline_days": 11,
        "expected_match": "RAD-015",  # VBE55-06NO7 = 600V 55A
    },
    {
        "id": "T-B03",
        "name": "Поставка силовых транзисторов MOSFET 1000В N-channel "
                "для импульсных источников питания",
        "okpd2": "26.11.12",
        "region": "Москва",
        "price_max": 150_000.0,
        "quantity_str": "10 шт",
        "deadline_days": 13,
        "expected_match": "RAD-006",  # IRFPG50 = 1000V MOSFET N-ch
    },

    # ════════════════════════════════════════
    # СЦЕНАРИЙ C: общее описание (~10%)
    # ════════════════════════════════════════
    {
        "id": "T-C01",
        "name": "Поставка электронных компонентов и средств промышленной "
                "автоматизации Siemens для модернизации АСУТП",
        "okpd2": "26.51",
        "region": "Ростовская область",
        "price_max": 3_200_000.0,
        "quantity_str": "",
        "deadline_days": 21,
        "expected_match": "RAD-011,RAD-014",  # multiple Siemens items
    },
    {
        "id": "T-C02",
        "name": "Поставка силовых полупроводниковых модулей "
                "для ремонта частотных преобразователей",
        "okpd2": "26.11.12",
        "region": "Свердловская область",
        "price_max": 1_800_000.0,
        "quantity_str": "",
        "deadline_days": 18,
        "expected_match": "RAD-001,RAD-004,RAD-005",  # broad IGBT match
    },
]


def get_test_tenders() -> list[dict]:
    return TEST_TENDERS


if __name__ == "__main__":
    from collections import Counter
    scenarios = Counter()
    for t in TEST_TENDERS:
        if t["id"].startswith("T-A"):
            scenarios["A"] += 1
        elif t["id"].startswith("T-B"):
            scenarios["B"] += 1
        else:
            scenarios["C"] += 1

    print(f"Test tenders: {len(TEST_TENDERS)} total")
    print(f"  Scenario A (exact PN):   {scenarios['A']}")
    print(f"  Scenario B (parametric): {scenarios['B']}")
    print(f"  Scenario C (broad):      {scenarios['C']}")
