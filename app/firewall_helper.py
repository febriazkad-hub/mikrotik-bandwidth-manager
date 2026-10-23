import re
from typing import Dict, Any, Tuple

class FirewallHelper:
    """Manages RouterOS FastTrack firewall rule non-destructively for accurate QoS"""

    FASTTRACK_COMMENT_TAG = "BWM: Disabled for Simple Queue QoS"

    @classmethod
    async def check_fasttrack_status(cls, exec_cmd_func) -> Dict[str, Any]:
        """
        Check if action=fasttrack-connection exists and whether it is enabled or disabled.
        Returns:
            {
                "exists": bool,
                "is_active": bool,  # True if rule is enabled (action=fasttrack-connection and disabled!=yes)
                "rule_id": Optional[str],
                "comment": str
            }
        """
        out = await exec_cmd_func('/ip firewall filter print terse where action=fasttrack-connection')
        if not out.strip():
            return {
                "exists": False,
                "is_active": False,
                "rule_id": None,
                "comment": "No FastTrack rule found"
            }

        # Parse output line
        line = out.strip().splitlines()[0]
        # Match rule ID at start
        id_match = re.match(r'^\s*(\*?[0-9a-fA-F]+|\d+)', line)
        rule_id = id_match.group(1) if id_match else None

        # Check disabled flag
        disabled = False
        if "disabled=yes" in line or " X " in line:
            disabled = True

        comment_match = re.search(r'comment="([^"]*)"', line)
        comment = comment_match.group(1) if comment_match else ""

        return {
            "exists": True,
            "is_active": not disabled,
            "rule_id": rule_id,
            "comment": comment
        }

    @classmethod
    async def disable_fasttrack_safe(cls, exec_cmd_func) -> Tuple[bool, str]:
        """
        Safely disables FastTrack rule so Simple Queues can shape traffic accurately.
        Non-destructive: Does NOT remove rule, only sets disabled=yes.
        """
        status = await cls.check_fasttrack_status(exec_cmd_func)
        if not status["exists"]:
            return True, "FastTrack rule tidak ditemukan (QoS sudah aktif secara alami)."
        
        if not status["is_active"]:
            return True, "FastTrack sudah dalam kondisi nonaktif (QoS aktif)."

        cmd = f'/ip firewall filter set [find action=fasttrack-connection] disabled=yes comment="{cls.FASTTRACK_COMMENT_TAG}"'
        await exec_cmd_func(cmd)
        
        # Verify
        updated = await cls.check_fasttrack_status(exec_cmd_func)
        if not updated["is_active"]:
            return True, "FastTrack berhasil dinonaktifkan secara aman. QoS Simple Queue kini beroperasi 100% akurat."
        return False, "Gagal menonaktifkan FastTrack di router."

    @classmethod
    async def restore_fasttrack(cls, exec_cmd_func) -> Tuple[bool, str]:
        """
        Restores FastTrack rule to enabled (disabled=no) upon Clean Detach or user request.
        """
        status = await cls.check_fasttrack_status(exec_cmd_func)
        if not status["exists"]:
            return True, "Tidak ada aturan FastTrack untuk dipulihkan."

        cmd = '/ip firewall filter set [find action=fasttrack-connection] disabled=no comment="defconf: fasttrack"'
        await exec_cmd_func(cmd)
        return True, "Aturan FastTrack berhasil dipulihkan ke kondisi aktif bawaan pabrik."
