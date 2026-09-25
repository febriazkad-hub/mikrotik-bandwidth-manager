import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.mikrotik_engine import engine_instance

async def clean_vips():
    vips = ["192.168.77.14", "192.168.77.16", "192.168.77.18", "192.168.77.20", "192.168.77.22", "192.168.77.23", "192.168.77.24", "192.168.77.28", "192.168.77.29"]
    target_str = ",".join([f"{x}/32" for x in vips])
    await engine_instance.exec_cmd(f'/queue simple set [find name="PRIORITY-FULL-GROUP"] target="{target_str}" max-limit=1G/1G')
    print("Cleaned VIP target list:", target_str)

if __name__ == "__main__":
    asyncio.run(clean_vips())
