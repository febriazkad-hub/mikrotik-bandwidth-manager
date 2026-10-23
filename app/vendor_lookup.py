import json
import os
import re
from typing import Dict

_OUI_CACHE: Dict[str, str] = {}

def _load_oui_database():
    global _OUI_CACHE
    if _OUI_CACHE:
        return
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "oui_lookup.json")
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                _OUI_CACHE = json.load(f)
        except Exception:
            _OUI_CACHE = {}

def get_vendor_from_mac(mac: str) -> str:
    """Resolve device hardware vendor from MAC address using offline OUI lookup"""
    if not mac:
        return "Unknown"
    _load_oui_database()
    clean_mac = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    if len(clean_mac) < 6:
        return "Unknown"
    prefix = f"{clean_mac[0:2]}:{clean_mac[2:4]}:{clean_mac[4:6]}"
    return _OUI_CACHE.get(prefix, "Generic Device")
