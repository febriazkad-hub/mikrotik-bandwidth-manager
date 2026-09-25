import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import asyncio
from app.mikrotik_engine import engine_instance

async def inspect():
    print("--- TEST 1: QUEUE VIP QUERY ---")
    out = await engine_instance.exec_cmd('/queue simple print terse where name=PRIORITY-FULL-GROUP')
    print("out:", repr(out))
    for part in out.split():
        if part.startswith("target="):
            print("target part:", part)

    print("\n--- TEST 2: CHECK CURRENT VIPS VS INDIVIDUAL LIMITS ---")
    devices = await engine_instance.get_all_devices()
    for d in devices:
        print(f"Device: {d.ip:15} | MAC: {d.mac} | Name: {d.alias_name:25} | Mode: {d.rate_mode:12} | Limit: {d.current_limit}")

asyncio.run(inspect())
