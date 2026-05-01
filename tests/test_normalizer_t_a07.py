"""Регрессионный тест на T-A07 (Allen-Bradley 1734-AENT).

Баг: PN extractor извлекал 'ETHERNET-IP' как candidate part number
вместо реального '1734-AENT'. Фикс: промышленные протоколы добавлены
в _STOPWORDS в src/normalizer_electronics.py.
"""
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
