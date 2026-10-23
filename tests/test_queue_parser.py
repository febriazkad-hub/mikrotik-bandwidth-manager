import pytest
from app.mikrotik_engine import extract_ips_from_target

def test_extract_ips_single_line():
    block = ' 0 name="BWM-BYPASS-GROUP" target=192.168.88.10/32,192.168.88.20/32 max-limit=1G/1G'
    ips = extract_ips_from_target(block)
    assert "192.168.88.10" in ips
    assert "192.168.88.20" in ips
    assert len(ips) == 2

def test_extract_ips_multi_line_wrapped():
    block = (
        ' 0    name="BWM-BYPASS-GROUP" target=192.168.88.10/32,192.168.88.20/32,\n'
        '       192.168.88.30/32,192.168.88.40/32 parent=none max-limit=1G/1G'
    )
    ips = extract_ips_from_target(block)
    assert ips == ["192.168.88.10", "192.168.88.20", "192.168.88.30", "192.168.88.40"]

def test_extract_ips_empty():
    block = ' 0 name="BWM-BYPASS-GROUP" target="" max-limit=1G/1G'
    ips = extract_ips_from_target(block)
    assert ips == []
