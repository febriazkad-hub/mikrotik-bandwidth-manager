import asyncio
from app.mikrotik_engine import engine_instance
async def main():
    print(await engine_instance.exec_cmd('/queue simple print detail where name="LIMIT-192.168.77.29"'))
asyncio.run(main())
