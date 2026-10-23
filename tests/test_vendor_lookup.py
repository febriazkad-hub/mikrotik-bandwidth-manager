import pytest
from app.vendor_lookup import get_vendor_from_mac

def test_vendor_oui_resolution():
    # Apple
    assert "Apple" in get_vendor_from_mac("00:03:93:11:22:33")
    assert "Apple" in get_vendor_from_mac("F4-F1-5A-AA-BB-CC")

    # Samsung
    assert "Samsung" in get_vendor_from_mac("00:07:AB:12:34:56")

    # Espressif (ESP32)
    assert "Espressif" in get_vendor_from_mac("24:0A:C4:00:11:22")

    # Raspberry Pi
    assert "Raspberry Pi" in get_vendor_from_mac("B8:27:EB:AA:BB:CC")

    # Intel
    assert "Intel" in get_vendor_from_mac("40:16:7E:00:11:22")

    # Realtek
    assert "Realtek" in get_vendor_from_mac("00:E0:4C:AA:BB:CC")

    # Unknown / fallback
    assert get_vendor_from_mac("02:00:00:00:00:00") == "Generic Device"
    assert get_vendor_from_mac("") == "Unknown"
