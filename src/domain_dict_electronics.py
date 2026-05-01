"""
domain_dict_electronics.py — Доменный словарь для микроэлектроники и электронных компонентов.

Заточен под номенклатуру Radal:
  - IGBT-модули, тиристоры, диоды
  - ПЛИС (Xilinx/Altera), микроконтроллеры (STM32, PIC, AVR)
  - ВЧ/СВЧ компоненты
  - Пассивные компоненты (резисторы, конденсаторы, индуктивности)
  - Коннекторы, датчики, реле
  - Промышленная автоматизация (Siemens, Allen-Bradley, Omron)

Ключевое отличие от промышленной номенклатуры (трубы, метизы):
  → Главный идентификатор = part number (буквенно-цифровой код)
  → Второй ключ = производитель (manufacturer)
  → Третий = параметры (напряжение, ток, корпус, частота)
"""

from __future__ import annotations
import re


# ══════════════════════════════════════════════
# 1. КАТЕГОРИИ ЭЛЕКТРОННЫХ КОМПОНЕНТОВ
# ══════════════════════════════════════════════
# Используется для blocking: группируем тендеры и номенклатуру
# по категории, чтобы не сравнивать IGBT с резисторами.

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "igbt": [
        "igbt", "игбт", "igbt-модуль", "igbt модуль",
        "insulated gate bipolar transistor",
    ],
    "thyristor": [
        "тиристор", "тиристорный модуль", "scr", "thyristor",
        "тиристорный блок", "тиристорная сборка",
    ],
    "diode": [
        "диод", "диодный модуль", "выпрямитель", "diode",
        "диод шоттки", "schottky", "стабилитрон", "zener",
    ],
    "mosfet": [
        "mosfet", "мосфет", "полевой транзистор", "fet",
    ],
    "plc_module": [
        "модуль ввода", "модуль вывода", "модуль i/o", "plc",
        "контроллер программируемый", "плк", "simatic",
        "модуль аналогового ввода", "модуль дискретного ввода",
        "модуль коммуникационный", "cpu модуль",
    ],
    "fpga_cpld": [
        "плис", "fpga", "cpld", "программируемая логика",
        "spartan", "virtex", "artix", "kintex", "zynq",
        "cyclone", "stratix", "max10",
    ],
    "microcontroller": [
        "микроконтроллер", "mcu", "stm32", "pic",
        "avr", "atmega", "esp32", "arm cortex",
    ],
    "memory": [
        "модуль памяти", "память", "dram", "sram", "sdram",
        "flash", "eeprom", "nand", "nor", "dimm", "sodimm",
    ],
    "connector": [
        "коннектор", "разъём", "разъем", "соединитель",
        "connector", "вилка", "розетка", "гнездо",
        "штекер", "клеммник", "клемма",
    ],
    "sensor": [
        "датчик", "сенсор", "sensor", "преобразователь",
        "термопара", "акселерометр", "гироскоп", "энкодер",
        "датчик давления", "датчик температуры",
        "датчик положения", "датчик холла", "hall",
    ],
    "capacitor": [
        "конденсатор", "capacitor", "cap", "ёмкость",
        "электролит", "керамический конденсатор", "mlcc",
    ],
    "resistor": [
        "резистор", "resistor", "сопротивление",
        "потенциометр", "подстроечный", "шунт",
    ],
    "inductor": [
        "индуктивность", "дроссель", "inductor", "катушка",
        "трансформатор", "transformer", "ферритовое кольцо",
    ],
    "relay": [
        "реле", "relay", "контактор", "пускатель",
        "твердотельное реле", "ssr",
    ],
    "power_supply": [
        "блок питания", "бп", "power supply", "psu",
        "dc-dc", "ac-dc", "преобразователь напряжения",
        "инвертор", "стабилизатор напряжения",
        "sitop", "tdk-lambda", "mean well",
    ],
    "led": [
        "светодиод", "led", "осветитель", "подсветка",
        "светодиодный модуль", "rgb led",
    ],
    "rf_component": [
        "вч компонент", "свч компонент", "rf", "microwave",
        "аттенюатор", "фильтр вч", "усилитель вч",
        "генератор", "смеситель", "циркулятор",
        "mini-circuits", "hittite",
    ],
    "optoelectronics": [
        "оптопара", "оптрон", "фотодиод", "фототранзистор",
        "оптоволокно", "лазерный диод",
    ],
    "drive": [
        "привод", "частотный преобразователь", "чрп", "vfd",
        "сервопривод", "серводвигатель", "инвертор",
        "drive", "altivar", "micromaster", "powerflex",
    ],
    "hmi_panel": [
        "панель оператора", "hmi", "операторская панель",
        "сенсорная панель", "touchscreen", "comfort panel",
    ],
}


# ══════════════════════════════════════════════
# 2. АББРЕВИАТУРЫ ЭЛЕКТРОНИКИ
# ══════════════════════════════════════════════
ABBREV_MAP: dict[str, str] = {
    # Компоненты
    "мк":     "микроконтроллер",
    "плис":   "ПЛИС",
    "бп":     "блок питания",
    "плк":    "ПЛК",
    "чрп":    "частотный преобразователь",
    "ибп":    "источник бесперебойного питания",

    # Параметры
    "в":      "В",       # вольт
    "а":      "А",       # ампер
    "вт":     "Вт",      # ватт
    "квт":    "кВт",
    "мгц":    "МГц",
    "ггц":    "ГГц",
    "мкф":    "мкФ",     # микрофарад
    "нф":     "нФ",      # нанофарад
    "пф":     "пФ",      # пикофарад
    "ком":    "кОм",
    "мом":    "МОм",
    "мгн":    "мГн",     # миллигенри
    "мкгн":   "мкГн",    # микрогенри

    # Корпуса
    "то-220": "TO-220",
    "to-220": "TO-220",
    "то-247": "TO-247",
    "to-247": "TO-247",
    "то-3":   "TO-3",
    "to-3":   "TO-3",
    "sot-23": "SOT-23",
    "soic":   "SOIC",
    "qfp":    "QFP",
    "bga":    "BGA",
    "tqfp":   "TQFP",
    "lqfp":   "LQFP",
    "dip":    "DIP",
    "sop":    "SOP",
    "smd":    "SMD",
}


# ══════════════════════════════════════════════
# 3. ПРОИЗВОДИТЕЛИ (варианты написания → каноническое)
# ══════════════════════════════════════════════
MANUFACTURER_ALIASES: dict[str, str] = {
    # Siemens
    "siemens":        "Siemens",
    "сименс":         "Siemens",
    "simatic":        "Siemens",

    # Allen-Bradley / Rockwell
    "allen-bradley":  "Allen-Bradley",
    "allen bradley":  "Allen-Bradley",
    "rockwell":       "Allen-Bradley",
    "ab":             "Allen-Bradley",

    # Texas Instruments
    "texas instruments": "Texas Instruments",
    "ti":             "Texas Instruments",
    "тексас":         "Texas Instruments",

    # STMicroelectronics
    "stmicroelectronics": "STMicroelectronics",
    "stm":            "STMicroelectronics",
    "st micro":       "STMicroelectronics",

    # Mitsubishi
    "mitsubishi":     "Mitsubishi Electric",
    "mitsubishi electric": "Mitsubishi Electric",
    "мицубиси":       "Mitsubishi Electric",

    # Analog Devices
    "analog devices": "Analog Devices",
    "adi":            "Analog Devices",

    # Xilinx (now AMD)
    "xilinx":         "Xilinx",
    "ксайлинкс":      "Xilinx",

    # Altera (now Intel)
    "altera":         "Altera",
    "альтера":        "Altera",

    # Omron
    "omron":          "Omron",
    "омрон":          "Omron",

    # Infineon
    "infineon":       "Infineon",
    "инфинеон":       "Infineon",

    # Vishay
    "vishay":         "Vishay",

    # TDK
    "tdk":            "TDK",
    "tdk-lambda":     "TDK-Lambda",

    # Fuji Electric
    "fuji":           "Fuji Electric",
    "fuji electric":  "Fuji Electric",
    "фуджи":          "Fuji Electric",

    # Microsemi (now Microchip)
    "microsemi":      "Microsemi",
    "microchip":      "Microchip",

    # SEMIKRON
    "semikron":       "SEMIKRON",
    "семикрон":       "SEMIKRON",

    # Mini-Circuits
    "mini-circuits":  "Mini-Circuits",
    "minicircuits":   "Mini-Circuits",

    # Qorvo
    "qorvo":          "Qorvo",
    "triquint":       "Qorvo",

    # AVX / KEMET
    "avx":            "AVX",
    "kemet":          "KEMET",

    # Cypress
    "cypress":        "Cypress",

    # Maxim
    "maxim":          "Maxim Integrated",
    "maxim integrated": "Maxim Integrated",
}


# ══════════════════════════════════════════════
# 4. REGEX: PART NUMBER EXTRACTION
# ══════════════════════════════════════════════
# Part numbers — буквенно-цифровые коды, обычно 5–25 символов.
# Примеры: CM1000E3U-34NF, 6ES7321-1BL00-0AA0, STM32F407VGT6,
#          XC7A35T-1CPG236C, IRFPG50, 7MBR75U2B060

# Паттерн: начинается с буквы/цифры, содержит mix букв+цифр,
# может содержать дефисы и слэши, минимум 4 символа.
RE_PART_NUMBER = re.compile(
    r'\b('
    r'[A-Z0-9]{2,}[\-/]?[A-Z0-9]{2,}'      # базовый: 2+ alnum, опц. дефис, 2+ alnum
    r'(?:[\-/][A-Z0-9]{1,})*'               # доп. секции через дефис/слэш
    r')\b',
    re.IGNORECASE
)

# Siemens-style: 6ES7321-1BL00-0AA0
RE_SIEMENS_PN = re.compile(
    r'\b(\d[A-Z]{2}\d{4}[\-]\d[A-Z]{2}\d{2}[\-]\d[A-Z]{2}\d)\b',
    re.IGNORECASE
)

# Электрические параметры
RE_VOLTAGE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:В|V|в|v|вольт|volt)\b',
    re.IGNORECASE
)
RE_CURRENT = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:А|A|а|a|ампер|amp)\b',
    re.IGNORECASE
)
RE_POWER = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:Вт|W|вт|кВт|kW)\b',
    re.IGNORECASE
)
RE_FREQUENCY = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:МГц|MHz|ГГц|GHz|кГц|kHz)\b',
    re.IGNORECASE
)
RE_CAPACITANCE = re.compile(
    r'(?<![A-Z0-9])(\d+(?:[.,]\d+)?)\s+(?:мкФ|µF|uF|нФ|nF|пФ|pF)\b',
    re.IGNORECASE
)
RE_RESISTANCE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(?:Ом|Ohm|кОм|kOhm|МОм|MOhm)\b',
    re.IGNORECASE
)


# ══════════════════════════════════════════════
# 5. НОРМАЛИЗАЦИЯ PART NUMBER
# ══════════════════════════════════════════════
def normalize_part_number(pn: str) -> str:
    """
    Приводит part number к каноническому виду для exact matching.

    Правила:
      1. Uppercase
      2. Убрать пробелы внутри
      3. Заменить слэши на дефисы
      4. Убрать trailing suffixes (-ND, -TR, /NOPB — это packaging codes)

    Примеры:
      "cm1000e3u-34nf"    → "CM1000E3U-34NF"
      "STM32F407 VGT6"    → "STM32F407VGT6"
      "6ES7 321-1BL00-0AA0" → "6ES7321-1BL00-0AA0"
      "LM317T/NOPB"       → "LM317T"
    """
    result = pn.strip().upper()
    result = result.replace(' ', '')
    result = result.replace('/', '-')

    # Убираем packaging suffixes (не влияют на идентификацию компонента)
    for suffix in ['-ND', '-TR', '-CT', '-NOPB', '/NOPB', '-PBF']:
        if result.endswith(suffix.upper()):
            result = result[:-len(suffix)]

    return result


# ══════════════════════════════════════════════
# 6. ПОИСК ПРОИЗВОДИТЕЛЯ В ТЕКСТЕ
# ══════════════════════════════════════════════
def find_manufacturer(text: str) -> str:
    """
    Ищет название производителя в тексте, возвращает каноническое имя.
    """
    text_lower = text.lower()
    # Сортируем по длине (длинные первые) чтобы "texas instruments" не перекрылся "ti"
    for alias in sorted(MANUFACTURER_ALIASES, key=len, reverse=True):
        if alias in text_lower:
            return MANUFACTURER_ALIASES[alias]
    return ""


# ══════════════════════════════════════════════
# 7. ОПРЕДЕЛЕНИЕ КАТЕГОРИИ
# ══════════════════════════════════════════════
def _keyword_matches(keyword: str, text_lower: str) -> bool:
    """
    Проверяет наличие ключевого слова в тексте с учётом границ слов.

    Левая граница строгая: keyword должно начинаться со слова —
    защищает от ложных срабатываний типа 'диод' внутри 'светодиод'
    или 'мк' внутри '100мкГн'.

    Правая граница ослаблена для кириллических окончаний: keyword
    'тиристор' матчит 'тиристор', 'тиристорный', 'тиристорного',
    'тиристоров' — это нужно для русских тендеров с любыми падежами.
    Латиница и цифры после keyword по-прежнему запрещены (это уже
    другое слово или part number).

    Работает для латиницы и кириллицы.
    """
    escaped = re.escape(keyword)
    pattern = r'(?<![a-zа-яё0-9])' + escaped + r'[а-яё]*(?![a-zа-яё0-9])'
    return bool(re.search(pattern, text_lower))


def detect_category(text: str) -> str:
    """
    Определяет категорию электронного компонента по ключевым словам.
    Возвращает ключ из CATEGORY_KEYWORDS или "" если не определена.
    """
    text_lower = text.lower()
    best_cat = ""
    best_score = 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if _keyword_matches(kw, text_lower))
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat if best_score > 0 else ""


# ══════════════════════════════════════════════
# 8. ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ
# ══════════════════════════════════════════════
def extract_electrical_params(text: str) -> dict:
    """
    Извлекает электрические параметры из текста.
    Возвращает: {"voltage": "1200", "current": "400", ...}
    """
    params: dict = {}

    m = RE_VOLTAGE.search(text)
    if m:
        params["voltage_v"] = float(m.group(1).replace(',', '.'))

    m = RE_CURRENT.search(text)
    if m:
        params["current_a"] = float(m.group(1).replace(',', '.'))

    m = RE_POWER.search(text)
    if m:
        params["power_w"] = float(m.group(1).replace(',', '.'))

    m = RE_FREQUENCY.search(text)
    if m:
        params["frequency"] = m.group(0)  # сохраняем с единицей

    m = RE_CAPACITANCE.search(text)
    if m:
        params["capacitance"] = m.group(0)

    m = RE_RESISTANCE.search(text)
    if m:
        params["resistance"] = m.group(0)

    return params
