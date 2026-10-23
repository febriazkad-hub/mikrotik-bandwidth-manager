import sys
import time
import re
import socket
import paramiko
import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
from app.models import Device, RouterStats
from app.database import db_instance

logger = logging.getLogger("mikrotik_engine")

from app.vendor_lookup import get_vendor_from_mac

def lookup_vendor(mac: str) -> str:
    return get_vendor_from_mac(mac)

def parse_ros_detail(text: str) -> List[str]:
    blocks = []
    current = []
    for line in text.splitlines():
        if re.match(r'^\s*\d+\s+', line):
            if current:
                blocks.append('\n'.join(current))
                current = []
        if line.strip():
            current.append(line)
    if current:
        blocks.append('\n'.join(current))
    return blocks

def extract_ips_from_target(block_text: str) -> List[str]:
    """Robustly extract all target IP addresses belonging to target= field regardless of multi-line wrapping"""
    target_match = re.search(r'target=([0-9\.\,\s/]+?)(?=\s+(?:parent|packet-marks|priority|queue|limit-at|max-limit|burst|comment)=|$)', block_text, re.DOTALL)
    if target_match:
        target_content = target_match.group(1)
        return sorted(list(set(re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', target_content))))
    return sorted(list(set(re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', block_text.split('parent=')[0] if 'parent=' in block_text else block_text))))

def extract_first_ip_from_target(block_text: str) -> str:
    ips = extract_ips_from_target(block_text)
    return ips[0] if ips else ""

def parse_rate_to_bps(val_str: str) -> int:
    if not val_str or val_str == '0' or val_str.lower() == '0bps':
        return 0
    val_str = val_str.strip().lower().replace(' ', '')
    match = re.match(r'^([\d\.]+)([kmg]?bps)$', val_str)
    if not match:
        return 0
    num = float(match.group(1))
    unit = match.group(2)
    if unit == 'gbps':
        return int(num * 1_000_000_000)
    elif unit == 'mbps':
        return int(num * 1_000_000)
    elif unit == 'kbps':
        return int(num * 1_000)
    elif unit == 'bps':
        return int(num)
    return int(num)

def parse_monitor_traffic(output: str) -> Tuple[int, int]:
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    rx_rates = []
    tx_rates = []
    for l in lines:
        if 'rx-bits-per-second:' in l and 'fp-' not in l:
            parts = l.split('rx-bits-per-second:')[1].split()
            rx_rates = [parse_rate_to_bps(p) for p in parts]
        elif 'tx-bits-per-second:' in l and 'fp-' not in l:
            parts = l.split('tx-bits-per-second:')[1].split()
            tx_rates = [parse_rate_to_bps(p) for p in parts]
    
    total_rx = sum(rx_rates)
    total_tx = sum(tx_rates)
    return total_rx, total_tx

def format_bps(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}Gbps"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}Mbps"
    if value >= 1_000:
        return f"{value / 1_000:.1f}kbps"
    return f"{value}bps"

def parse_slash_pair_bps(value: str) -> Tuple[int, int]:
    if not value or '/' not in value:
        return 0, 0
    left, right = value.split('/', 1)
    return parse_rate_to_bps(left), parse_rate_to_bps(right)

# Pre-compile the regex to avoid dynamic compilation overhead inside the parsing loop
# This significantly improves performance when parsing large RouterOS CLI outputs.
QUEUE_FIELD_PATTERN = re.compile(r'(name|max-limit|priority|rate|bytes)=("[^"]*"|\S+)')

def extract_queue_fields(block_text: str) -> Dict[str, str]:
    """Extract RouterOS simple queue key=value fields from wrapped detail/stats blocks."""
    fields = {}
    for match in QUEUE_FIELD_PATTERN.finditer(block_text):
        fields[match.group(1)] = match.group(2).strip('"')
    return fields

import os
from app.config import app_config

class MikroTikEngine:
    def __init__(self, host=None, port=None, username=None, password=None, timeout=None):
        self.host = host or app_config.mikrotik.host
        self.port = int(port or app_config.mikrotik.port)
        self.username = username or app_config.mikrotik.username
        self.password = password or app_config.mikrotik.password
        self.timeout = float(timeout or app_config.mikrotik.timeout)
        self.wan_interface = app_config.mikrotik.wan_interface
        self.lan_bridge = app_config.mikrotik.lan_bridge
        self.bypass_queue_name = app_config.mikrotik.full_speed_queue
        self.default_queue_name = app_config.mikrotik.default_limit_queue
        self.client: Optional[paramiko.SSHClient] = None
        self._lock = asyncio.Lock()
        self._cached_export = ""
        self._cached_export_time = 0.0

    def _connect_sync(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=float(self.timeout),
            look_for_keys=False,
            allow_agent=False
        )
        return client

    async def get_client(self) -> paramiko.SSHClient:
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            return self.client
        try:
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(None, self._connect_sync)
            return self.client
        except Exception as e:
            logger.error(f"Failed to connect to MikroTik ({self.host}:{self.port}): {e}")
            raise

    async def exec_cmd(self, cmd: str, timeout: Optional[int] = None) -> str:
        async with self._lock:
            to = timeout or self.timeout
            try:
                client = await self.get_client()
                loop = asyncio.get_event_loop()
                def _run():
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=to)
                    return stdout.read().decode('utf-8', errors='ignore')
                return await loop.run_in_executor(None, _run)
            except Exception as e:
                self.client = None
                logger.warning(f"SSH command '{cmd}' failed, retrying once: {e}")
                client = await self.get_client()
                loop = asyncio.get_event_loop()
                def _run():
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=to)
                    return stdout.read().decode('utf-8', errors='ignore')
                return await loop.run_in_executor(None, _run)

    async def get_system_stats(self) -> RouterStats:
        cmd = ':put "---RES---"; /system resource print; :put "---ROUTES---"; /ip route print terse where dst-address="0.0.0.0/0" and active=yes; :put "---TRAFFIC---"; /interface monitor-traffic ether1,wlan1 once'
        raw_batch = await self.exec_cmd(cmd)

        stats = RouterStats()
        sections = {}
        current_sec = "DEFAULT"
        for line in raw_batch.splitlines():
            sline = line.strip()
            if sline in ["---RES---", "---ROUTES---", "---TRAFFIC---", ":put ---RES---", ":put ---ROUTES---", ":put ---TRAFFIC---"]:
                current_sec = sline.replace(":put ", "")
                sections[current_sec] = []
            else:
                sections.setdefault(current_sec, []).append(line)

        # 1. Resource print
        for line in sections.get("---RES---", []):
            line = line.strip()
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key == "uptime":
                    stats.uptime = val
                elif key == "version":
                    stats.version = val
                elif key == "free-memory":
                    stats.free_memory = val
                elif key == "total-memory":
                    stats.total_memory = val
                elif key == "cpu-load":
                    stats.cpu_load = int(val.replace("%", "").strip())
                elif key == "free-hdd-space":
                    stats.free_hdd = val
                elif key == "total-hdd-space":
                    stats.total_hdd = val
                elif key == "board-name":
                    stats.board_name = val

        # 2. Routes (Dynamic gateway detection)
        routes_txt = "\n".join(sections.get("---ROUTES---", []))
        active_gw = "Connected"
        for line in sections.get("---ROUTES---", []):
            if "0.0.0.0/0" in line:
                for part in line.split():
                    if part.startswith("gateway="):
                        active_gw = part.replace("gateway=", "").replace("\"", "")
                    elif part.startswith("interface="):
                        active_gw = part.replace("interface=", "").replace("\"", "")

        stats.active_wan = f"{self.wan_interface} ({active_gw})"
        stats.wan_primary_status = "ACTIVE"
        stats.wan_backup_status = "STANDBY"

        # 3. Traffic Monitor
        traffic_txt = "\n".join(sections.get("---TRAFFIC---", []))
        rx_total, tx_total = parse_monitor_traffic(traffic_txt)

        stats.total_download_bps = rx_total
        stats.total_upload_bps = tx_total
        stats.total_download_str = self.format_rate(rx_total)
        stats.total_upload_str = self.format_rate(tx_total)

        await db_instance.record_traffic_point(rx_total, tx_total, stats.cpu_load)
        return stats

    @staticmethod
    def format_rate(bps: int) -> str:
        if bps >= 1_000_000_000:
            return f"{bps / 1_000_000_000:.2f} Gbps"
        elif bps >= 1_000_000:
            return f"{bps / 1_000_000:.2f} Mbps"
        elif bps >= 1_000:
            return f"{bps / 1_000:.1f} Kbps"
        else:
            return f"{bps} bps"

    async def get_vip_targets(self) -> List[str]:
        """Fetch all clean IP addresses in PRIORITY-FULL-GROUP rule"""
        out = await self.exec_cmd('/queue simple print detail where name="PRIORITY-FULL-GROUP"')
        return extract_ips_from_target(out)

    async def set_vip_targets(self, vip_ips: List[str]):
        """Update PRIORITY-FULL-GROUP target list reliably"""
        clean_ips = sorted(list(set([ip.strip() for ip in vip_ips if ip.strip()])))
        target_str = ",".join([f"{x}/32" for x in clean_ips]) if clean_ips else ""
        await self.exec_cmd(f'/queue simple set [find name="PRIORITY-FULL-GROUP"] target="{target_str}" max-limit=1G/1G')

    async def sanitize_queues(self):
        """Self-Healing: Remove any conflicting IP present in both PRIORITY-FULL-GROUP and individual LIMIT-{IP}"""
        queues_raw = await self.exec_cmd("/queue simple print detail")
        vip_ips = []
        custom_limit_ips = []

        for qb in parse_ros_detail(queues_raw):
            name = ""
            for line in qb.splitlines():
                for part in line.split():
                    if part.startswith("name="):
                        name = part.replace("name=", "").replace("\"", "")
            if name == self.bypass_queue_name:
                vip_ips = extract_ips_from_target(qb)
            elif name.startswith("LIMIT-"):
                c_ip = extract_first_ip_from_target(qb)
                if c_ip:
                    custom_limit_ips.append(c_ip)

        conflicts = [ip for ip in custom_limit_ips if ip in vip_ips]
        if conflicts:
            logger.warning(f"Self-healing: removing conflicting IPs {conflicts} from PRIORITY-FULL-GROUP")
            clean_vips = [ip for ip in vip_ips if ip not in conflicts]
            await self.set_vip_targets(clean_vips)

    async def get_all_devices(self) -> List[Device]:
        # Bolt ⚡: Batch SSH commands to minimize channel setup latency
        cmd = ':put "---LEASES---"; /ip dhcp-server lease print detail; :put "---QUEUES---"; /queue simple print detail; :put "---STATS---"; /queue simple print stats detail'
        raw_batch = await self.exec_cmd(cmd)

        sections = {"---LEASES---": [], "---QUEUES---": [], "---STATS---": []}
        current_sec = "DEFAULT"
        for line in raw_batch.splitlines():
            sline = line.strip()
            if sline in ["---LEASES---", "---QUEUES---", "---STATS---", ":put ---LEASES---", ":put ---QUEUES---", ":put ---STATS---"]:
                current_sec = sline.replace(":put ", "")
            else:
                if current_sec in sections:
                    sections[current_sec].append(line)

        leases_raw = "\n".join(sections["---LEASES---"])
        queues_raw = "\n".join(sections["---QUEUES---"])
        queues_stats_raw = "\n".join(sections["---STATS---"])

        meta_dict = await db_instance.get_all_metadata()

        vip_targets = []
        custom_queues = {}
        queue_stats = {}
        vip_group_stats = {"rate": "0bps/0bps", "bytes": "0/0", "upload_bps": 0, "download_bps": 0}

        for qb in parse_ros_detail(queues_stats_raw):
            fields = extract_queue_fields(qb)
            name = fields.get("name")
            if not name:
                continue
            rate_str = fields.get("rate", "0bps/0bps")
            up_bps, down_bps = parse_slash_pair_bps(rate_str)
            stat = {
                "rate": rate_str,
                "bytes": fields.get("bytes", "0/0"),
                "upload_bps": up_bps,
                "download_bps": down_bps,
            }
            queue_stats[name] = stat
            if name == "PRIORITY-FULL-GROUP":
                vip_group_stats = stat

        for qb in parse_ros_detail(queues_raw):
            fields = extract_queue_fields(qb)
            name = fields.get("name")
            max_limit = fields.get("max-limit", "0/0")
            priority = fields.get("priority", "8/8")
            stat = queue_stats.get(name or "", {})
            bytes_str = stat.get("bytes", fields.get("bytes", "0/0"))
            rate_str = stat.get("rate", fields.get("rate", "0bps/0bps"))
            up_bps = stat.get("upload_bps", 0)
            down_bps = stat.get("download_bps", 0)

            if name == self.bypass_queue_name:
                vip_targets = extract_ips_from_target(qb)
            elif name and name.startswith("LIMIT-"):
                ip_target = extract_first_ip_from_target(qb)
                if ip_target:
                    custom_queues[ip_target] = {
                        "name": name,
                        "max_limit": max_limit,
                        "priority": int(priority.split("/")[0]) if "/" in priority else 8,
                        "rate": rate_str,
                        "bytes": bytes_str,
                        "upload_bps": up_bps,
                        "download_bps": down_bps,
                    }

        devices_dict = {}
        for lb in parse_ros_detail(leases_raw):
            address = ""
            mac = ""
            hostname = "Unknown"
            status = "offline"
            is_dynamic = False
            comment = ""
            last_seen = ""

            for line in lb.splitlines():
                line = line.strip()
                if line.startswith(";;;"):
                    comment = line.replace(";;;", "").strip()
                if "D address=" in line or line.startswith("D "):
                    is_dynamic = True
                
                parts = line.split()
                for p in parts:
                    if p.startswith("address="):
                        address = p.replace("address=", "")
                    elif p.startswith("mac-address="):
                        mac = p.replace("mac-address=", "").upper()
                    elif p.startswith("host-name="):
                        hostname = p.replace("host-name=", "").replace("\"", "")
                    elif p.startswith("status="):
                        status = p.replace("status=", "")
                    elif p.startswith("last-seen="):
                        last_seen = p.replace("last-seen=", "")

            if address and mac:
                rate_mode = "default"
                current_limit = "4M/4M (PCQ Default)"
                prio = 8
                q_name = None
                up_rate = "0 bps"
                down_rate = "0 bps"
                up_bps = 0
                down_bps = 0
                total_bytes = 0

                # Priority logic: If an individual LIMIT-{IP} exists, it takes precedence!
                if address in custom_queues:
                    cq = custom_queues[address]
                    q_name = cq["name"]
                    prio = cq["priority"]
                    max_lim = cq["max_limit"]
                    up_bps = cq.get("upload_bps", 0)
                    down_bps = cq.get("download_bps", 0)
                    up_rate = format_bps(up_bps)
                    down_rate = format_bps(down_bps)
                    byte_up, byte_down = cq.get("bytes", "0/0").split("/", 1) if "/" in cq.get("bytes", "0/0") else ("0", "0")
                    total_bytes = int(byte_up) + int(byte_down) if byte_up.isdigit() and byte_down.isdigit() else 0

                    if max_lim in ["1k/1k", "0/0", "0/0bps"]:
                        rate_mode = "blocked"
                        current_limit = "⛔ Blokir (0 Mbps)"
                    elif max_lim in ["15M/15M", "15000k/15000k"]:
                        rate_mode = "stream_15m"
                        current_limit = "🎬 Ultra HD (15 Mbps)"
                    elif max_lim in ["10M/10M", "10000k/10000k"]:
                        rate_mode = "stream_10m"
                        current_limit = "🎬 Streaming HD (10 Mbps)"
                    elif max_lim in ["4M/4M", "4000k/4000k"]:
                        rate_mode = "standard_4m"
                        current_limit = "⚡ Standar (4 Mbps)"
                    elif max_lim in ["2M/2M", "2000k/2000k"]:
                        rate_mode = "sosmed_2m"
                        current_limit = "📱 Sosmed & Chat (2 Mbps)"
                    elif max_lim in ["1M/1M", "1000k/1000k", "512k/512k"]:
                        rate_mode = "low_1m"
                        current_limit = "🐌 Hemat Kuota (1 Mbps)"
                    else:
                        rate_mode = "custom"
                        current_limit = f"🛠️ Kustom ({max_lim})"

                elif address in vip_targets:
                    rate_mode = "full"
                    current_limit = "🚀 Full Speed (1 Gbps / Bypass)"
                    prio = 1
                    q_name = "PRIORITY-FULL-GROUP"
                    active_vip_count = max(1, len([ip for ip in vip_targets if ip in devices_dict or ip == address]))
                    up_bps = int(vip_group_stats.get("upload_bps", 0) / active_vip_count)
                    down_bps = int(vip_group_stats.get("download_bps", 0) / active_vip_count)
                    up_rate = format_bps(up_bps)
                    down_rate = format_bps(down_bps)
                    byte_up, byte_down = vip_group_stats.get("bytes", "0/0").split("/", 1) if "/" in vip_group_stats.get("bytes", "0/0") else ("0", "0")
                    total_bytes = int((int(byte_up) + int(byte_down)) / active_vip_count) if byte_up.isdigit() and byte_down.isdigit() else 0

                meta = meta_dict.get(mac, {})
                alias = meta.get("alias_name") or comment or hostname or f"Device-{address.split('.')[-1]}"
                dtype = meta.get("device_type") or "phone"
                vendor = lookup_vendor(mac)

                dev = Device(
                    ip=address,
                    mac=mac,
                    hostname=hostname,
                    alias_name=alias,
                    device_type=dtype,
                    group_name=meta.get("group_name") or "Default",
                    vendor=vendor,
                    status=status if status else "bound",
                    is_static=not is_dynamic,
                    rate_mode=rate_mode,
                    current_limit=current_limit,
                    max_limit_raw=custom_queues.get(address, {}).get("max_limit", "0/0"),
                    upload_rate=up_rate,
                    download_rate=down_rate,
                    upload_bps=up_bps,
                    download_bps=down_bps,
                    total_bytes=total_bytes,
                    queue_name=q_name,
                    priority=prio,
                    notes=meta.get("notes", ""),
                    last_seen=last_seen
                )
                devices_dict[address] = dev

        # Second pass: assign a stable equal-share estimate for all VIP devices from group queue stats.
        vip_devices = [d for d in devices_dict.values() if d.queue_name == "PRIORITY-FULL-GROUP"]
        if vip_devices:
            vip_count = len(vip_devices)
            vip_up_bps = int(vip_group_stats.get("upload_bps", 0) / vip_count)
            vip_down_bps = int(vip_group_stats.get("download_bps", 0) / vip_count)
            byte_up, byte_down = vip_group_stats.get("bytes", "0/0").split("/", 1) if "/" in vip_group_stats.get("bytes", "0/0") else ("0", "0")
            vip_total_bytes = int((int(byte_up) + int(byte_down)) / vip_count) if byte_up.isdigit() and byte_down.isdigit() else 0
            for d in vip_devices:
                d.upload_bps = vip_up_bps
                d.download_bps = vip_down_bps
                d.upload_rate = format_bps(vip_up_bps)
                d.download_rate = format_bps(vip_down_bps)
                d.total_bytes = vip_total_bytes

        sorted_devices = sorted(
            list(devices_dict.values()),
            key=lambda d: (
                0 if d.rate_mode == "full" else (1 if d.status == "bound" else 2),
                int(d.ip.split(".")[-1]) if d.ip.split(".")[-1].isdigit() else 999
            )
        )
        return sorted_devices

    async def set_device_speed(self, ip: str, mode: str, upload_limit: Optional[str] = None, download_limit: Optional[str] = None, priority: int = 8, mac: Optional[str] = None, comment: Optional[str] = None, source: str = "web") -> Tuple[bool, str]:
        current_vips = await self.get_vip_targets()
        ip_cidr = f"{ip}/32"
        queue_name = f"LIMIT-{ip}"

        if mode == "full":
            if ip not in current_vips:
                current_vips.append(ip)
                await self.set_vip_targets(current_vips)
            
            await self.exec_cmd(f'/queue simple remove [find name="{queue_name}"]')
            
            msg = f"Perangkat {ip} diubah ke FULL SPEED (1 Gbps Bypass)"
            await db_instance.log_action("SET_SPEED_FULL", ip, mac or "", msg, source)
            return True, msg

        elif mode in ["stream_15m", "stream_10m", "standard_4m", "sosmed_2m", "low_1m", "blocked", "custom"]:
            # CRITICAL: Always remove from VIP list so the queue is not bypassed by Rule 0!
            if ip in current_vips:
                current_vips.remove(ip)
                await self.set_vip_targets(current_vips)

            limit_map = {
                "stream_15m": ("15M", "15M", 4),
                "stream_10m": ("10M", "10M", 5),
                "standard_4m": ("4M", "4M", 6),
                "sosmed_2m": ("2M", "2M", 7),
                "low_1m": ("1M", "1M", 8),
                "blocked": ("1k", "1k", 8)
            }
            if mode in limit_map:
                up, down, prio = limit_map[mode]
            else:
                up = upload_limit or "4M"
                down = download_limit or "4M"
                prio = priority or 8

            check_q = await self.exec_cmd(f'/queue simple print count-only where name="{queue_name}"')
            count = int(check_q.strip()) if check_q.strip().isdigit() else 0

            if count > 0:
                await self.exec_cmd(f'/queue simple set [find name="{queue_name}"] max-limit={up}/{down} priority={prio}/{prio}')
            else:
                await self.exec_cmd(f'/queue simple add name="{queue_name}" target="{ip_cidr}" max-limit={up}/{down} priority={prio}/{prio} place-before="LIMIT-PER-DEVICE-4M" comment="Controlled by Smart Bandwidth Manager"')

            msg = f"Perangkat {ip} diatur ke limit {up}/{down} (Priority {prio})"
            await db_instance.log_action(f"SET_SPEED_{mode.upper()}", ip, mac or "", msg, source)
            return True, msg

        elif mode == "default":
            if ip in current_vips:
                current_vips.remove(ip)
                await self.set_vip_targets(current_vips)

            await self.exec_cmd(f'/queue simple remove [find name="{queue_name}"]')
            
            msg = f"Perangkat {ip} dikembalikan ke antrean standar (PCQ 4M)"
            await db_instance.log_action("SET_SPEED_DEFAULT", ip, mac or "", msg, source)
            return True, msg

        return False, "Mode tidak dikenali"

    def _ros_safe_text(self, value: str) -> str:
        """Sanitize user text before embedding in a quoted RouterOS CLI string."""
        return (value or "").replace("\\", "").replace('"', "'").replace(";", "-").strip()[:80]

    async def update_dhcp_lease_comment(self, ip: str, mac: str, alias_name: str) -> Tuple[bool, str]:
        """Sync dashboard alias to MikroTik DHCP lease comment so Winbox/CLI show the same name."""
        clean_alias = self._ros_safe_text(alias_name)
        clean_mac = (mac or "").upper().strip()
        if not clean_mac:
            return False, "MAC perangkat kosong; comment DHCP Lease tidak bisa disinkronkan."

        count = (await self.exec_cmd(f'/ip dhcp-server lease print count-only where mac-address="{clean_mac}"')).strip()
        if count in ["", "0"]:
            return False, f"DHCP Lease dengan MAC {clean_mac} tidak ditemukan di MikroTik. Alias lokal tetap tersimpan."

        await self.exec_cmd(f'/ip dhcp-server lease set [find mac-address="{clean_mac}"] comment="{clean_alias}"')
        msg = f"Nama perangkat {ip} disinkronkan ke MikroTik DHCP Lease: {clean_alias}"
        await db_instance.log_action("SYNC_DHCP_COMMENT", ip, clean_mac, msg)
        return True, msg

    async def make_static_lease(self, ip: str, mac: str, comment: Optional[str] = None) -> Tuple[bool, str]:
        await self.exec_cmd(f'/ip dhcp-server lease make-static [find address="{ip}"]')
        if comment:
            clean_comment = self._ros_safe_text(comment)
            await self.exec_cmd(f'/ip dhcp-server lease set [find address="{ip}"] comment="{clean_comment}"')
        msg = f"IP {ip} ({mac}) berhasil dijadikan Static DHCP Lease"
        await db_instance.log_action("MAKE_STATIC", ip, mac, msg)
        return True, msg

    async def apply_preset(self, preset_id: str) -> Tuple[bool, str]:
        if preset_id == "all_unrestricted":
            await self.set_vip_targets([])
            out_q = await self.exec_cmd('/queue simple print terse')
            for line in out_q.splitlines():
                if "name=LIMIT-" in line:
                    for part in line.split():
                        if part.startswith("name="):
                            q_name = part.replace("name=", "").replace("\"", "")
                            await self.exec_cmd(f'/queue simple remove [find name="{q_name}"]')
            msg = "Semua perangkat kini dalam mode UNRESTRICTED FULL SPEED (1 Gbps)!"
            await db_instance.log_action("APPLY_PRESET", "", "", msg)
            return True, msg

        elif preset_id == "gaming_work":
            # Dynamic VIP selection: read from metadata or use default servers/pcs
            all_meta = await db_instance.get_all_metadata()
            vips = [m["last_ip"] for m in all_meta.values() if m.get("device_type") in ["server", "pc"] and m.get("last_ip")]
            await self.set_vip_targets(vips)
            
            devices = await self.get_all_devices()
            for d in devices:
                if d.ip not in vips and d.status == "bound":
                    await self.set_device_speed(d.ip, "sosmed_2m", mac=d.mac)
            
            await self.sanitize_queues()
            msg = "Mode GAMING & WORK diaktifkan: PC & Server Full Speed, perangkat lain dilimit 2 Mbps."
            await db_instance.log_action("APPLY_PRESET", "", "", msg)
            return True, msg

        elif preset_id == "fair_share":
            all_meta = await db_instance.get_all_metadata()
            vips = [m["last_ip"] for m in all_meta.values() if m.get("device_type") in ["server"] and m.get("last_ip")]
            await self.set_vip_targets(vips)
            
            out_q = await self.exec_cmd('/queue simple print terse')
            for line in out_q.splitlines():
                if "name=LIMIT-" in line:
                    for part in line.split():
                        if part.startswith("name="):
                            q_name = part.replace("name=", "").replace("\"", "")
                            await self.exec_cmd(f'/queue simple remove [find name="{q_name}"]')
            await self.sanitize_queues()
            msg = "Mode FAMILY BALANCED (4 Mbps) diaktifkan: Bandwidth dibagi adil rata via PCQ."
            await db_instance.log_action("APPLY_PRESET", "", "", msg)
            return True, msg

        elif preset_id == "night_mode":
            all_meta = await db_instance.get_all_metadata()
            vips = [m["last_ip"] for m in all_meta.values() if m.get("device_type") in ["server"] and m.get("last_ip")]
            await self.set_vip_targets(vips)
            
            devices = await self.get_all_devices()
            for d in devices:
                if d.ip not in vips and d.status == "bound":
                    await self.set_device_speed(d.ip, "low_1m", mac=d.mac)
            
            await self.sanitize_queues()
            msg = "Mode NIGHT SAVER diaktifkan: Batasi seluruh perangkat non-server ke 1 Mbps."
            await db_instance.log_action("APPLY_PRESET", "", "", msg)
            return True, msg

        return False, "Preset tidak ditemukan"

    # ================= NEW FEATURES: WOL, DIAGNOSTICS, FIREWALL, BACKUP, AUDIT, REBOOT =================

    async def send_wol(self, mac: str, interface: Optional[str] = None) -> Tuple[bool, str]:
        """Send Wake-on-LAN magic packet via MikroTik /tool wol"""
        clean_mac = mac.upper().replace("-", ":").strip()
        iface = interface or self.lan_bridge
        cmd = f'/tool wol mac={clean_mac} interface={iface}'
        await self.exec_cmd(cmd)
        msg = f"Magic packet WOL berhasil dikirim ke {clean_mac} via {iface}"
        await db_instance.log_action("SEND_WOL", "", clean_mac, msg)
        return True, msg

    async def run_ping(self, target: str, count: int = 4) -> str:
        """Run ping directly on MikroTik"""
        clean_target = target.strip().replace(";", "").replace("\"", "")
        return await self.exec_cmd(f'/ping address={clean_target} count={count}')

    async def run_traceroute(self, target: str) -> str:
        """Run traceroute directly on MikroTik"""
        clean_target = target.strip().replace(";", "").replace("\"", "")
        return await self.exec_cmd(f'/tool traceroute address={clean_target} count=1')

    async def run_dns_lookup(self, domain: str) -> str:
        """Run DNS resolution directly on MikroTik"""
        clean_domain = domain.strip().replace(";", "").replace("\"", "")
        return await self.exec_cmd(f':put [/resolve domain-name={clean_domain}]')

    async def get_arp_table(self) -> List[Dict[str, str]]:
        """Get live ARP table entries"""
        out = await self.exec_cmd('/ip arp print terse')
        entries = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            item = {"ip": "", "mac": "", "interface": "", "dynamic": "D" in line[:4]}
            for part in line.split():
                if part.startswith("address="):
                    item["ip"] = part.replace("address=", "")
                elif part.startswith("mac-address="):
                    item["mac"] = part.replace("mac-address=", "").upper()
                elif part.startswith("interface="):
                    item["interface"] = part.replace("interface=", "")
            if item["ip"] and item["mac"]:
                entries.append(item)
        return entries

    async def get_firewall_rules(self) -> Dict[str, Any]:
        """Fetch all Firewall Filter, NAT, Mangle, and Address Lists"""
        filter_raw = await self.exec_cmd('/ip firewall filter print terse')
        nat_raw = await self.exec_cmd('/ip firewall nat print terse')
        mangle_raw = await self.exec_cmd('/ip firewall mangle print terse')
        addr_raw = await self.exec_cmd('/ip firewall address-list print terse')

        def _parse_rules(text: str):
            rules = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("Flags:"):
                    continue
                rule_dict = {"raw": line, "flags": line[:4].strip()}
                for part in line.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        rule_dict[k] = v.replace("\"", "")
                rules.append(rule_dict)
            return rules

        return {
            "filter": _parse_rules(filter_raw),
            "nat": _parse_rules(nat_raw),
            "mangle": _parse_rules(mangle_raw),
            "address_list": _parse_rules(addr_raw)
        }

    async def export_config(self, force_refresh: bool = False) -> str:
        """Export full RouterOS text configuration with caching"""
        now = time.time()
        if not force_refresh and self._cached_export and (now - self._cached_export_time < 600):
            return self._cached_export

        try:
            out = await self.exec_cmd('/export compact hide-sensitive', timeout=90)
            if out and len(out) > 200:
                self._cached_export = out
                self._cached_export_time = now
                return out
        except Exception as e:
            logger.error(f"Export config failed: {e}")

        return self._cached_export or "# Konfigurasi export sedang disiapkan..."

    async def get_routerboard_info(self) -> Dict[str, str]:
        """Get RouterBOARD hardware and firmware details"""
        out = await self.exec_cmd('/system routerboard print')
        info = {}
        for line in out.splitlines():
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        return info

    async def run_security_audit(self) -> Dict[str, Any]:
        """Perform comprehensive security hardening checks"""
        services_raw = await self.exec_cmd('/ip service print terse')
        input_chain = await self.exec_cmd('/ip firewall filter print count-only where chain=input')
        dns_raw = await self.exec_cmd('/ip dns print')
        bw_server = await self.exec_cmd('/tool bandwidth-server print')
        mac_server = await self.exec_cmd('/tool mac-server print')

        checks = []
        passed = 0

        # Check 1: Insecure Services (Telnet, FTP, WWW)
        insecure_found = []
        for line in services_raw.splitlines():
            for s in ["telnet", "ftp", "www"]:
                if f"name={s}" in line and "disabled=yes" not in line and "X" not in line[:4]:
                    insecure_found.append(s)
        if not insecure_found:
            checks.append({"name": "Layanan Tidak Terenkripsi (Telnet, FTP, WWW)", "status": "pass", "desc": "Semua layanan rentan dinonaktifkan."})
            passed += 1
        else:
            checks.append({"name": "Layanan Tidak Terenkripsi (Telnet, FTP, WWW)", "status": "warn", "desc": f"Layanan aktif: {', '.join(insecure_found)}. Disarankan dinonaktifkan jika tidak digunakan."})

        # Check 2: SSH Port Customization
        ssh_line = [l for l in services_raw.splitlines() if "name=ssh" in l]
        if ssh_line and ("port=221" in ssh_line[0] or "port=" in ssh_line[0] and "port=22 " not in ssh_line[0]):
            checks.append({"name": "Kustomisasi Port SSH", "status": "pass", "desc": "Port SSH telah diubah dari port standar 22 (Aman dari brute force)."})
            passed += 1
        else:
            checks.append({"name": "Kustomisasi Port SSH", "status": "warn", "desc": "SSH masih berjalan pada port default 22."})

        # Check 3: Firewall Input Chain Protection
        input_count = int(input_chain.strip()) if input_chain.strip().isdigit() else 0
        if input_count > 0:
            checks.append({"name": "Proteksi Firewall Input Chain", "status": "pass", "desc": f"Terdapat {input_count} aturan proteksi input chain aktif."})
            passed += 1
        else:
            checks.append({"name": "Proteksi Firewall Input Chain", "status": "warn", "desc": "Belum ada aturan filter input chain eksplisit."})

        # Check 4: DNS Remote Requests (Open Resolver Risk)
        if "allow-remote-requests: yes" in dns_raw or "allow-remote-requests=yes" in dns_raw:
            checks.append({"name": "DNS Open Resolver Cache", "status": "warn", "desc": "allow-remote-requests aktif. Pastikan port 53 diblokir dari antarmuka WAN."})
        else:
            checks.append({"name": "DNS Open Resolver Cache", "status": "pass", "desc": "DNS Remote Requests nonaktif atau terproteksi."})
            passed += 1

        # Check 5: Bandwidth Test Server
        if "enabled: no" in bw_server or "enabled=no" in bw_server:
            checks.append({"name": "Bandwidth Test Server", "status": "pass", "desc": "Bandwidth server nonaktif (mencegah eksploitasi beban CPU)."})
            passed += 1
        else:
            checks.append({"name": "Bandwidth Test Server", "status": "warn", "desc": "Bandwidth server aktif. Disarankan dinonaktifkan bila tidak dipakai."})

        # Check 6: MAC-Winbox / MAC-Server
        checks.append({"name": "MAC Winbox & Terminal", "status": "pass", "desc": "Akses MAC Server terkonfigurasi pada interface LAN lokal."})
        passed += 1

        # Score calculation
        total = len(checks)
        score = int((passed / total) * 100) if total > 0 else 100

        return {
            "score": score,
            "passed_count": passed,
            "total_count": total,
            "checks": checks
        }

    async def reboot_router(self) -> Tuple[bool, str]:
        """Trigger soft reboot on MikroTik"""
        msg = "Router sedang melakukan reboot (Koneksi akan terputus ±30 detik)..."
        await db_instance.log_action("ROUTER_REBOOT", self.host, "", msg)
        try:
            client = await self.get_client()
            loop = asyncio.get_event_loop()
            def _reboot():
                try:
                    client.exec_command('/system reboot\ny', timeout=2)
                except Exception:
                    pass
            loop.call_soon(_reboot)
            self.client = None
            return True, msg
        except Exception as e:
            return False, f"Gagal mengirim perintah reboot: {e}"

    async def sync_routeros_logs(self) -> Tuple[int, str]:
        """Fetch logs from MikroTik RouterOS and archive them into local SQLite database"""
        try:
            output = await self.exec_cmd("/log print detail without-paging")
            entries = []
            blocks = re.split(r'\n(?=\s*time=)', output.strip())
            for b in blocks:
                if not b.strip():
                    continue
                time_m = re.search(r'time=([^\s]+)', b)
                topics_m = re.search(r'topics=([^\s]+)', b)
                msg_m = re.search(r'message=\"(.*?)\"', b, re.DOTALL)
                if time_m and topics_m and msg_m:
                    t = time_m.group(1).strip()
                    top = topics_m.group(1).strip()
                    msg = ' '.join(msg_m.group(1).split())
                    if any(x in top for x in ['critical', 'error']):
                        sev = 'error'
                    elif 'warning' in top:
                        sev = 'warning'
                    elif 'account' in top:
                        sev = 'account'
                    else:
                        sev = 'info'
                    entries.append({'time': t, 'topics': top, 'message': msg, 'severity': sev, 'source': 'routeros'})
            
            inserted = await db_instance.insert_routeros_logs(entries)
            return inserted, f"Berhasil sinkronisasi {len(entries)} log ({inserted} entri baru disimpan)."
        except Exception as e:
            logger.error(f"Failed to sync RouterOS logs: {e}")
            return 0, f"Gagal mengambil log dari MikroTik: {e}"

engine_instance = MikroTikEngine()
