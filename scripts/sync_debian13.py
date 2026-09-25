import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.mikrotik_engine import engine_instance
from app.database import db_instance

async def sync():
    await db_instance.init_db()
    # 1. Update SQLite DB
    await db_instance.upsert_device_alias(
        mac='00:E0:4C:A6:32:5C',
        ip='192.168.77.16',
        alias_name='PC Debian 13 Server (CasaOS)',
        device_type='server',
        group_name='Server & Core',
        notes='Debian 13 Trixie Server / CasaOS'
    )

    # 2. Update MikroTik Lease
    await engine_instance.exec_cmd('/ip dhcp-server lease make-static [find address="192.168.77.16"]')
    await engine_instance.exec_cmd('/ip dhcp-server lease set [find address="192.168.77.16"] comment="PRIORITY FULL SPEED azka PC Debian 13 Server"')
    
    # 3. Clean up stale .23 lease
    await engine_instance.exec_cmd('/ip dhcp-server lease remove [find address="192.168.77.23" and status="waiting"]')

    # 4. Clean up VIP queue targets to include .16
    vips = ["192.168.77.14", "192.168.77.16", "192.168.77.18", "192.168.77.20", "192.168.77.22", "192.168.77.24", "192.168.77.28", "192.168.77.29"]
    target_str = ",".join([f"{x}/32" for x in vips])
    await engine_instance.exec_cmd(f'/queue simple set [find name="PRIORITY-FULL-GROUP"] target="{target_str}" max-limit=1G/1G')
    
    print("Debian 13 (.16) sync completed successfully!")

if __name__ == "__main__":
    asyncio.run(sync())
