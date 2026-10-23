import logging
from typing import Dict, Any, List, Tuple, Optional
import httpx
from app.adapters.base import BaseRouterAdapter
from app.adapters.ros6 import RouterOS6Adapter
from app.models import Device, SystemStats

logger = logging.getLogger("ros7_adapter")

class RouterOS7Adapter(BaseRouterAdapter):
    """RouterOS v7 Dual-Transport Adapter (Native REST API with SSH Fallback)"""

    def __init__(self, host: str, port: int, username: str, password: str, rest_port: int = 443, **kwargs):
        super().__init__(host, port, username, password, **kwargs)
        self.rest_port = rest_port
        self.base_url = f"https://{self.host}:{self.rest_port}/rest"
        self.ssh_fallback = RouterOS6Adapter(host, port, username, password, **kwargs)
        self.use_rest = False
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        # Check if REST API is responsive
        try:
            async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
                res = await client.get(
                    f"{self.base_url}/system/resource",
                    auth=(self.username, self.password)
                )
                if res.status_code == 200:
                    self.use_rest = True
                    logger.info("RouterOS v7 REST API detected and operational.")
                    return True
        except Exception as e:
            logger.info(f"REST API not reachable ({e}), falling back to SSH CLI.")
            self.use_rest = False

        # Fallback to SSH
        return await self.ssh_fallback.connect()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        await self.ssh_fallback.disconnect()

    async def get_system_stats(self) -> SystemStats:
        if not self.use_rest:
            return await self.ssh_fallback.get_system_stats()
        try:
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                res = await client.get(
                    f"{self.base_url}/system/resource",
                    auth=(self.username, self.password)
                )
                data = res.json()
                total_mem = int(data.get("total-memory", 0))
                free_mem = int(data.get("free-memory", 0))
                total_hdd = int(data.get("total-hdd-space", 0))
                free_hdd = int(data.get("free-hdd-space", 0))

                return SystemStats(
                    cpu_load=int(data.get("cpu-load", 0)),
                    free_memory=f"{free_mem // (1024*1024)}MB",
                    total_memory=f"{total_mem // (1024*1024)}MB",
                    free_hdd=f"{free_hdd // (1024*1024)}MB",
                    total_hdd=f"{total_hdd // (1024*1024)}MB",
                    uptime=data.get("uptime", "0s"),
                    board_name=data.get("board-name", "MikroTik RouterOS v7"),
                    version=data.get("version", "v7"),
                    active_wan="ether1",
                    total_download_str="0 bps",
                    total_upload_str="0 bps",
                    total_download_raw=0,
                    total_upload_raw=0
                )
        except Exception as e:
            logger.warning(f"REST API stats fetch failed: {e}. Falling back to SSH.")
            return await self.ssh_fallback.get_system_stats()

    async def get_all_devices(self) -> List[Device]:
        # Gracefully delegates device mapping to SSH CLI parser which contains full ARP+Lease cross-referencing
        return await self.ssh_fallback.get_all_devices()

    async def set_device_rate(
        self, 
        ip: str, 
        mode: str, 
        upload_limit: Optional[str] = None, 
        download_limit: Optional[str] = None
    ) -> Tuple[bool, str]:
        return await self.ssh_fallback.set_device_rate(ip, mode, upload_limit, download_limit)

    async def send_wol(self, mac: str, interface: Optional[str] = None) -> Tuple[bool, str]:
        return await self.ssh_fallback.send_wol(mac, interface)

    async def reboot(self) -> Tuple[bool, str]:
        return await self.ssh_fallback.reboot()

    async def exec_cmd(self, cmd: str) -> str:
        return await self.ssh_fallback.exec_cmd(cmd)
