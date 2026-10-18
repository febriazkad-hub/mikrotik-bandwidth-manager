from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Device(BaseModel):
    ip: str
    mac: str
    hostname: Optional[str] = "Unknown"
    alias_name: Optional[str] = None
    device_type: str = "phone"  # phone, pc, laptop, tv, iot, server, guest, unknown
    group_name: str = "Default"
    vendor: Optional[str] = "Unknown Vendor"
    status: str = "offline"     # bound, waiting, online, offline
    is_static: bool = False
    rate_mode: str = "default"  # full, standard, streaming, sosmed, low, custom, blocked, default
    current_limit: str = "4M/4M (PCQ)"
    max_limit_raw: str = "0/0"
    upload_rate: str = "0 bps"
    download_rate: str = "0 bps"
    upload_bps: int = 0
    download_bps: int = 0
    total_bytes: int = 0
    queue_name: Optional[str] = None
    priority: int = 8
    notes: Optional[str] = ""
    last_seen: Optional[str] = None

class SpeedChangeRequest(BaseModel):
    ip: str
    mac: Optional[str] = None
    mode: str  # 'full', 'stream_15m', 'stream_10m', 'standard_4m', 'sosmed_2m', 'low_1m', 'blocked', 'default', 'custom'
    upload_limit: Optional[str] = None
    download_limit: Optional[str] = None
    priority: Optional[int] = 8
    comment: Optional[str] = None
    duration_minutes: Optional[int] = None

class DeviceAliasRequest(BaseModel):
    ip: str
    mac: str
    alias_name: str
    device_type: Optional[str] = "phone"
    group_name: Optional[str] = "Default"
    notes: Optional[str] = ""

class MakeStaticRequest(BaseModel):
    ip: str
    mac: str
    comment: Optional[str] = None

class PresetApplyRequest(BaseModel):
    preset_id: str

class ScheduleRule(BaseModel):
    id: Optional[int] = None
    device_ip: str
    device_mac: Optional[str] = None
    device_alias: Optional[str] = None
    name: str
    start_time: str   # Format HH:MM (e.g. "22:00")
    end_time: str     # Format HH:MM (e.g. "06:00")
    action_mode: str  # blocked, low_1m, sosmed_2m, standard_4m, full
    upload_limit: Optional[str] = None
    download_limit: Optional[str] = None
    days_of_week: str = "0,1,2,3,4,5,6"  # 0=Mon, 6=Sun
    is_enabled: bool = True

class RouterStats(BaseModel):
    cpu_load: int = 0
    free_memory: str = "0 MiB"
    total_memory: str = "0 MiB"
    free_hdd: str = "0 MiB"
    total_hdd: str = "0 MiB"
    uptime: str = "0s"
    version: str = "RouterOS"
    board_name: str = "MikroTik"
    active_wan: str = "ether1"
    wan_primary_status: str = "CONNECTED"
    wan_backup_status: str = "STANDBY"
    total_download_bps: int = 0
    total_upload_bps: int = 0
    total_download_str: str = "0 bps"
    total_upload_str: str = "0 bps"
    total_devices_online: int = 0
    total_devices_all: int = 0

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
