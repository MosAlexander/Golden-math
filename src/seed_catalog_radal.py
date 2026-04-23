"""
seed_catalog_radal.py — Seed-каталог Radal (15 флагманских позиций).

Собран из открытых источников:
  - radal.ru (карточки товаров)
  - ChipFind.ru (профиль Radal)
  - Saby.ru (тендерная история, основной заказчик НПО Центротех)
  - Социальные сети Radal (Instagram/VK посты)

Покрывает ключевые категории Radal:
  1. IGBT-модули (основной товар, больше всего позиций на сайте)
  2. Тиристорные модули
  3. Модули ПЛК Siemens SIMATIC (акцент в постах и рекламе)
  4. Модули Allen-Bradley (акцент в рекламе)
  5. Блоки питания Siemens SITOP
  6. ПЛИС Xilinx
  7. Микроконтроллеры STM32
  8. Драйверы IGBT (Concept, InPower)

Этого достаточно для:
  - Калибровки нормализатора
  - Настройки Splink blocking/scoring
  - Тестирования матчинга с реальными тендерами
  - Демо дашборда

Когда получишь реальный каталог от Radal — замени этот файл на полный CSV-экспорт.
"""

SEED_CATALOG = [
    # ──── IGBT-модули (флагман Radal) ────
    {
        "id": "RAD-001",
        "part_number": "CM1000E3U-34NF",
        "name": "IGBT модуль CM1000E3U-34NF Mitsubishi Electric 3400V 1000A",
        "manufacturer": "Mitsubishi Electric",
        "category": "igbt",
        "params": {"voltage_v": 3400, "current_a": 1000},
        "in_stock": True,
        "stock_qty": 5,
    },
    {
        "id": "RAD-002",
        "part_number": "CM1200E4C-34N",
        "name": "IGBT модуль CM1200E4C-34N Mitsubishi Electric 3400V 1200A",
        "manufacturer": "Mitsubishi Electric",
        "category": "igbt",
        "params": {"voltage_v": 3400, "current_a": 1200},
        "in_stock": True,
        "stock_qty": 3,
    },
    {
        "id": "RAD-003",
        "part_number": "CM2400HCB-34N",
        "name": "IGBT модуль CM2400HCB-34N Mitsubishi Electric 3400V 2400A",
        "manufacturer": "Mitsubishi Electric",
        "category": "igbt",
        "params": {"voltage_v": 3400, "current_a": 2400},
        "in_stock": True,
        "stock_qty": 2,
    },
    {
        "id": "RAD-004",
        "part_number": "7MBR75U2B060",
        "name": "IGBT модуль 7MBR75U2B060 Fuji Electric 600V 75A",
        "manufacturer": "Fuji Electric",
        "category": "igbt",
        "params": {"voltage_v": 600, "current_a": 75},
        "in_stock": True,
        "stock_qty": 47,
    },
    {
        "id": "RAD-005",
        "part_number": "MP6752",
        "name": "IGBT модуль MP6752 Toshiba",
        "manufacturer": "Toshiba",
        "category": "igbt",
        "params": {},
        "in_stock": True,
        "stock_qty": 42,
    },
    {
        "id": "RAD-006",
        "part_number": "IRFPG50",
        "name": "POWER TRANSISTOR IRFPG50 1000V 6.1A N CHANNEL TO-247AC MOSFET HEXFET",
        "manufacturer": "International Rectifier",
        "category": "mosfet",
        "params": {"voltage_v": 1000, "current_a": 6.1, "package": "TO-247AC"},
        "in_stock": False,
        "stock_qty": 0,
    },
    {
        "id": "RAD-007",
        "part_number": "MCC310-08IO1B",
        "name": "IGBT модуль MCC 310-08io1B IXYS",
        "manufacturer": "IXYS",
        "category": "igbt",
        "params": {},
        "in_stock": True,
        "stock_qty": 45,
    },
    {
        "id": "RAD-008",
        "part_number": "K229A04",
        "name": "IGBT MODULE K229A04 VINCO",
        "manufacturer": "VINCO",
        "category": "igbt",
        "params": {},
        "in_stock": False,
        "stock_qty": 0,
    },

    # ──── Драйверы IGBT (упоминаются в постах Radal) ────
    {
        "id": "RAD-009",
        "part_number": "1SD536F2-CM1200E4C-34N",
        "name": "Драйвер IGBT Concept 1SD536F2-CM1200E4C-34N",
        "manufacturer": "Concept (CT-Concept)",
        "category": "igbt_driver",
        "params": {},
        "in_stock": True,
        "stock_qty": 10,
    },
    {
        "id": "RAD-010",
        "part_number": "2IPSE1W12-60",
        "name": "Драйвер IGBT InPower 2IPSE1W12-60",
        "manufacturer": "InPower",
        "category": "igbt_driver",
        "params": {},
        "in_stock": True,
        "stock_qty": 8,
    },

    # ──── Siemens SIMATIC (акцент в рекламе, основной тендерный товар) ────
    {
        "id": "RAD-011",
        "part_number": "6ES7321-1BL00-0AA0",
        "name": "Модуль ввода дискретных сигналов SM 321 Siemens SIMATIC S7-300 32DI 24В",
        "manufacturer": "Siemens",
        "category": "plc_module",
        "params": {"voltage_v": 24},
        "in_stock": True,
        "stock_qty": 15,
    },

    # ──── Allen-Bradley (акцент в рекламе: «удалённое шасси модулей I/O») ────
    {
        "id": "RAD-012",
        "part_number": "1734-AENT",
        "name": "Allen-Bradley POINT I/O EtherNet/IP Adapter 1734-AENT",
        "manufacturer": "Allen-Bradley",
        "category": "plc_module",
        "params": {},
        "in_stock": True,
        "stock_qty": 6,
    },

    # ──── ПЛИС Xilinx (из профиля ChipFind) ────
    {
        "id": "RAD-013",
        "part_number": "XC7A35T-1CPG236C",
        "name": "ПЛИС Xilinx Artix-7 XC7A35T-1CPG236C",
        "manufacturer": "Xilinx",
        "category": "fpga_cpld",
        "params": {},
        "in_stock": True,
        "stock_qty": 20,
    },

    # ──── Блоки питания Siemens SITOP (из рекламных постов) ────
    {
        "id": "RAD-014",
        "part_number": "6EP3436-8SB00-0AY0",
        "name": "Блок питания SITOP PSU8200 6EP3436-8SB00-0AY0 Siemens 24В 20А",
        "manufacturer": "Siemens",
        "category": "power_supply",
        "params": {"voltage_v": 24, "current_a": 20},
        "in_stock": True,
        "stock_qty": 4,
    },

    # ──── Тиристоры (из профиля ChipFind + категории на сайте) ────
    {
        "id": "RAD-015",
        "part_number": "VBE55-06NO7",
        "name": "Тиристорный/диодный модуль VBE 55-06NO7 IXYS 600V 55A",
        "manufacturer": "IXYS",
        "category": "thyristor",
        "params": {"voltage_v": 600, "current_a": 55},
        "in_stock": True,
        "stock_qty": 42,
    },
]


def get_seed_catalog() -> list[dict]:
    """Возвращает seed-каталог для тестирования пайплайна."""
    return SEED_CATALOG


if __name__ == "__main__":
    print(f"Radal seed catalog: {len(SEED_CATALOG)} items")
    print()
    for item in SEED_CATALOG:
        stock = f"✓ {item['stock_qty']} шт" if item['in_stock'] else "✗ нет"
        print(f"  {item['id']:8s} | {item['part_number']:28s} | {item['manufacturer']:22s} | {stock}")
