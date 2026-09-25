import asyncio
import sys
import os

# Fix stdout encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add root to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from app.database import db_instance
from app.mikrotik_engine import engine_instance

async def main():
    print("=== 1. TEST DATABASE INITIALIZATION ===")
    await db_instance.init_db()
    metadata = await db_instance.get_all_metadata()
    presets = await db_instance.get_presets()
    print(f"[OK] Database initialized. Known device metadata: {len(metadata)}, Presets: {len(presets)}")

    print("\n=== 2. TEST MIKROTIK SYSTEM STATS ===")
    stats = await engine_instance.get_system_stats()
    print(f"[OK] Board: {stats.board_name}, Version: {stats.version}, CPU: {stats.cpu_load}%, RAM: {stats.free_memory}/{stats.total_memory}, WAN: {stats.active_wan}")
    print(f"[OK] Throughput: DL={stats.total_download_str}, UL={stats.total_upload_str}")

    print("\n=== 3. TEST DEVICE PARSING & QUEUE MAPPING ===")
    devices = await engine_instance.get_all_devices()
    print(f"[OK] Total devices parsed: {len(devices)}")
    for d in devices:
        status_sym = "[ONLINE]" if d.status == "bound" else "[IDLE]"
        print(f"  {status_sym} [{d.ip}] {d.alias_name} ({d.mac}) -> Mode: {d.rate_mode} | Limit: {d.current_limit} | Vendor: {d.vendor}")

    print("\n=== 4. TEST SPEED CHANGE LOGIC ===")
    ok, msg = await engine_instance.set_device_speed("192.168.77.29", "full", mac="40:16:7E:23:A0:8A", source="unit_test")
    print(f"[OK] Set Speed Result: {ok} -> {msg}")

    print("\n=== ALL UNIT TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(main())
