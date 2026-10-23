"""
Self-contained RouterOS Mock Engine for offline unit testing & CI/CD.
Simulates MikroTik RouterOS v6 / v7 command execution without physical router hardware.
"""

from typing import Dict, Optional, Tuple

class RouterOSMock:
    def __init__(self, ros_version: str = "6.49.15", model: str = "hAP lite", arch: str = "smips"):
        self.version = ros_version
        self.model = model
        self.arch = arch
        self.fasttrack_disabled = False
        self.queues: Dict[str, dict] = {
            "BWM-BYPASS-GROUP": {"target": "192.168.88.10/32", "max-limit": "1G/1G", "priority": "1/1"},
            "BWM-PARENT": {"target": "192.168.88.0/24", "max-limit": "100M/100M", "priority": "8/8"}
        }
        self.leases = [
            {"address": "192.168.88.10", "mac-address": "40:16:7E:11:22:33", "host-name": "Workstation", "status": "bound"},
            {"address": "192.168.88.20", "mac-address": "00:E0:4C:AA:BB:CC", "host-name": "Home-Server", "status": "bound"},
            {"address": "192.168.88.30", "mac-address": "24:0A:C4:01:02:03", "host-name": "ESP32-SmartRelay", "status": "bound"}
        ]

    async def exec_cmd(self, cmd: str) -> str:
        cmd = cmd.strip()

        # System resource
        if "/system resource print" in cmd:
            return (
                f"                   uptime: 5d12h30m\n"
                f"                  version: {self.version}\n"
                f"               build-time: Jun/10/2024 10:00:00\n"
                f"              free-memory: 18.5MiB\n"
                f"             total-memory: 32.0MiB\n"
                f"                      cpu: MIPS 24KEc V1.5\n"
                f"                cpu-count: 1\n"
                f"            cpu-frequency: 650MHz\n"
                f"                 cpu-load: 14%\n"
                f"               free-hdd-space: 4.8MiB\n"
                f"              total-hdd-space: 16.0MiB\n"
                f"             architecture-name: {self.arch}\n"
                f"                   board-name: {self.model}\n"
                f"                     platform: MikroTik\n"
            )

        # WAN Route detection
        if '/ip route print terse' in cmd and '0.0.0.0/0' in cmd:
            return ' 0 A S  dst-address=0.0.0.0/0 gateway=192.168.1.1 gateway-status="192.168.1.1 reachable via ether1" distance=1 scope=30 target-scope=10'

        # DHCP Client
        if '/ip dhcp-client print terse' in cmd:
            return ' 0   interface=ether1 add-default-route=yes use-peer-dns=yes use-peer-ntp=yes status=bound address=192.168.1.50/24'

        # LAN Bridge
        if '/interface bridge print terse' in cmd:
            return ' 0 R  name=bridge mtu=auto actual-mtu=1500 l2mtu=1598 mac-address=00:0C:42:AA:BB:CC arp=enabled priority=0x8000 auto-mac=no admin-mac=00:0C:42:AA:BB:CC'

        # IP Address
        if '/ip address print terse' in cmd:
            return ' 0   address=192.168.88.1/24 network=192.168.88.0 interface=bridge actual-interface=bridge'

        # FastTrack check & manipulation
        if '/ip firewall filter print terse where action=fasttrack-connection' in cmd:
            if self.fasttrack_disabled:
                return ' 0 X  chain=forward action=fasttrack-connection connection-state=established,related disabled=yes comment="BWM: Disabled for Simple Queue QoS"'
            return ' 0    chain=forward action=fasttrack-connection connection-state=established,related disabled=no comment="defconf: fasttrack"'

        if '/ip firewall filter set [find action=fasttrack-connection]' in cmd:
            if 'disabled=yes' in cmd:
                self.fasttrack_disabled = True
            elif 'disabled=no' in cmd:
                self.fasttrack_disabled = False
            return ""

        # Simple Queue operations
        if '/queue simple print terse' in cmd:
            lines = []
            idx = 0
            for name, q in self.queues.items():
                p = f'parent="{q.get("parent")}"' if "parent" in q else 'parent=none'
                lines.append(f' {idx}   name="{name}" target="{q.get("target")}" max-limit={q.get("max-limit")} priority={q.get("priority")} {p} queue=default/default')
                idx += 1
            return "\n".join(lines)

        if '/queue simple add' in cmd:
            import re
            name_m = re.search(r'name="([^"]+)"', cmd)
            target_m = re.search(r'target="([^"]*)"', cmd)
            limit_m = re.search(r'max-limit=([^\s]+)', cmd)
            prio_m = re.search(r'priority=([^\s]+)', cmd)
            if name_m:
                qname = name_m.group(1)
                self.queues[qname] = {
                    "target": target_m.group(1) if target_m else "",
                    "max-limit": limit_m.group(1) if limit_m else "0/0",
                    "priority": prio_m.group(1) if prio_m else "8/8"
                }
            return ""

        if '/queue simple remove' in cmd:
            if 'parent=' in cmd:
                self.queues = {k: v for k, v in self.queues.items() if v.get("parent") is None}
            if 'name="BWM-PARENT"' in cmd:
                self.queues.pop("BWM-PARENT", None)
            if 'name="BWM-BYPASS-GROUP"' in cmd:
                self.queues.pop("BWM-BYPASS-GROUP", None)
            return ""

        # DHCP Leases
        if '/ip dhcp-server lease print terse' in cmd:
            lines = []
            idx = 0
            for l in self.leases:
                lines.append(f' {idx}   address={l["address"]} mac-address={l["mac-address"]} host-name="{l["host-name"]}" status={l["status"]}')
                idx += 1
            return "\n".join(lines)

        # Traffic monitor
        if '/interface monitor-traffic' in cmd:
            return "     name: ether1\n  rx-bits-per-second: 15420000\n  tx-bits-per-second: 2450000\n"

        # Tool WOL
        if '/tool wol' in cmd:
            return ""

        # Fallback default
        return ""
