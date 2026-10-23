import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional
from app.adapters.base import BaseRouterAdapter
from app.models import Device, SystemStats
from app.mikrotik_engine import engine_instance

logger = logging.getLogger("ros6_adapter")

class RouterOS6Adapter(BaseRouterAdapter):
    """RouterOS v6 SSH CLI Adapter with precompiled regex and batch command optimization"""

    def __init__(self, host: str, port: int, username: str, password: str, **kwargs):
        super().__init__(host, port, username, password, **kwargs)
        self.engine = engine_instance

    async def connect(self) -> bool:
        client = await self.engine.get_client()
        return client is not None

    async def disconnect(self) -> None:
        self.engine.close_client()

    async def get_system_stats(self) -> SystemStats:
        return await self.engine.get_system_stats()

    async def get_all_devices(self) -> List[Device]:
        return await self.engine.get_all_devices()

    async def set_device_rate(
        self, 
        ip: str, 
        mode: str, 
        upload_limit: Optional[str] = None, 
        download_limit: Optional[str] = None
    ) -> Tuple[bool, str]:
        return await self.engine.set_device_speed(ip, mode, upload_limit, download_limit)

    async def send_wol(self, mac: str, interface: Optional[str] = None) -> Tuple[bool, str]:
        return await self.engine.wake_on_lan(mac, interface)

    async def reboot(self) -> Tuple[bool, str]:
        return await self.engine.reboot_router()

    async def exec_cmd(self, cmd: str) -> str:
        return await self.engine.exec_cmd(cmd)
