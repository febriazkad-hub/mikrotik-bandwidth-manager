import asyncio
from app.mikrotik_engine import engine_instance

async def main():
    print("=== QUEUE STATS ===")
    out = await engine_instance.exec_cmd('/queue simple print stats')
    print(out)

if __name__ == "__main__":
    asyncio.run(main())
