import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.mikrotik_engine import engine_instance

async def test():
    cmd = ':put "---RES---"; /system resource print; :put "---ROUTES---"; /ip route print terse where dst-address="0.0.0.0/0" and active=yes; :put "---TRAFFIC---"; /interface monitor-traffic ether1,wlan1 once'
    out = await engine_instance.exec_cmd(cmd)
    print("Batch Response:\n" + out)

if __name__ == "__main__":
    asyncio.run(test())
