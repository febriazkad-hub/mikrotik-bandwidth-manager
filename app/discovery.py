import re
from typing import Dict, Any, Optional

class RouterDiscovery:
    """Zero-Config Discovery Engine for MikroTik RouterOS"""

    @staticmethod
    def parse_key_value(line: str) -> Dict[str, str]:
        """Parses RouterOS terse format '0  name=bridge ...' into dict"""
        res = {}
        for match in re.finditer(r'([a-zA-Z0-9_\-]+)=("([^"]*)"|([^\s]+))', line):
            key = match.group(1)
            val = match.group(3) if match.group(3) is not None else match.group(4)
            res[key] = val
        return res

    @classmethod
    def detect_wan_interface(cls, route_output: str, dhcp_client_output: str = "") -> str:
        """Detect the primary WAN interface from default routes (0.0.0.0/0) or DHCP client"""
        # 1. Check active default route
        for line in route_output.splitlines():
            line = line.strip()
            if not line:
                continue
            kv = cls.parse_key_value(line)
            gateway_status = kv.get("gateway-status", "")
            # e.g., 'gateway-status=192.168.1.1 reachable via ether1'
            gw_match = re.search(r'reachable via\s+([a-zA-Z0-9_\-]+)', gateway_status)
            if gw_match:
                return gw_match.group(1)
            
            # Direct gateway interface
            gw = kv.get("gateway", "")
            if gw and not re.match(r'^\d+\.\d+\.\d+\.\d+$', gw) and gw != "%":
                return gw
            
            interface = kv.get("interface", "")
            if interface:
                return interface

        # 2. Fallback to DHCP client interface
        for line in dhcp_client_output.splitlines():
            kv = cls.parse_key_value(line)
            if kv.get("status") == "bound" and kv.get("interface"):
                return kv.get("interface")

        # 3. Universal factory fallback
        return "ether1"

    @classmethod
    def detect_lan_bridge(cls, bridge_output: str, ip_address_output: str = "") -> str:
        """Detect the primary LAN bridge interface"""
        # 1. Discover configured bridges
        bridges = []
        for line in bridge_output.splitlines():
            line = line.strip()
            if not line:
                continue
            kv = cls.parse_key_value(line)
            bname = kv.get("name")
            if bname and kv.get("disabled", "no") == "no":
                bridges.append(bname)

        if bridges:
            # Common factory default names take precedence
            for preferred in ["bridge", "bridge-local", "bridgeLAN", "br-lan"]:
                if preferred in bridges:
                    return preferred
            return bridges[0]

        # 2. Fallback: Check IP addresses bound to interface
        for line in ip_address_output.splitlines():
            kv = cls.parse_key_value(line)
            iface = kv.get("interface", "")
            if "bridge" in iface.lower():
                return iface

        # 3. Universal factory fallback
        return "bridge"

    @classmethod
    def parse_version_and_arch(cls, resource_output: str) -> Dict[str, Any]:
        """Detect RouterOS major version (v6 vs v7), architecture, and model"""
        res = {
            "version": "unknown",
            "major_version": 6,
            "architecture": "unknown",
            "board_name": "MikroTik Router"
        }
        for line in resource_output.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            parts = line.split(":", 1)
            k = parts[0].strip().lower()
            v = parts[1].strip()
            if k == "version":
                res["version"] = v
                match = re.match(r'^(\d+)', v)
                if match:
                    res["major_version"] = int(match.group(1))
            elif k in ["architecture-name", "architecture"]:
                res["architecture"] = v
            elif k in ["board-name", "model"]:
                res["board_name"] = v
        return res
