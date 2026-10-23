from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
from app.models import Device, SystemStats

class BaseRouterAdapter(ABC):
    """Abstract Base Class for MikroTik RouterOS Adapters"""

    def __init__(self, host: str, port: int, username: str, password: str, **kwargs):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.kwargs = kwargs

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the router"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the router"""
        pass

    @abstractmethod
    async def get_system_stats(self) -> SystemStats:
        """Fetch system statistics (CPU, RAM, HDD, Traffic, Uptime)"""
        pass

    @abstractmethod
    async def get_all_devices(self) -> List[Device]:
        """Fetch all connected devices from DHCP leases and ARP table"""
        pass

    @abstractmethod
    async def set_device_rate(
        self, 
        ip: str, 
        mode: str, 
        upload_limit: Optional[str] = None, 
        download_limit: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Apply bandwidth rate limiting or bypass for target IP"""
        pass

    @abstractmethod
    async def send_wol(self, mac: str, interface: Optional[str] = None) -> Tuple[bool, str]:
        """Send Wake-on-LAN magic packet to target MAC address"""
        pass

    @abstractmethod
    async def reboot(self) -> Tuple[bool, str]:
        """Soft-reboot the router"""
        pass

    @abstractmethod
    async def exec_cmd(self, cmd: str) -> str:
        """Execute a raw router command and return output"""
        pass
