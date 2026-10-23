import re
from typing import Tuple, Dict, Any

class QueueProvisioner:
    """Zero-Config Auto-Provisioning for MikroTik Simple Queues"""

    @classmethod
    async def check_queues_exist(cls, exec_cmd_func, parent_name: str, bypass_name: str) -> Dict[str, bool]:
        """Check if BWM core queues already exist on the router"""
        out = await exec_cmd_func('/queue simple print terse')
        has_parent = False
        has_bypass = False
        for line in out.splitlines():
            if f"name={parent_name}" in line or f'name="{parent_name}"' in line:
                has_parent = True
            if f"name={bypass_name}" in line or f'name="{bypass_name}"' in line:
                has_bypass = True
        return {"parent": has_parent, "bypass": has_bypass}

    @classmethod
    async def provision_baseline(
        cls, 
        exec_cmd_func, 
        parent_name: str = "BWM-PARENT", 
        bypass_name: str = "BWM-BYPASS-GROUP",
        target_subnet: str = "192.168.88.0/24",
        max_limit: str = "100M/100M"
    ) -> Tuple[bool, str]:
        """
        Idempotent baseline provisioning:
        Creates root Parent Queue and Bypass Group queue without disrupting internet connectivity.
        """
        status = await cls.check_queues_exist(exec_cmd_func, parent_name, bypass_name)
        actions = []

        # 1. Create Bypass / Full-speed Queue at position 0 (Priority 1)
        if not status["bypass"]:
            cmd_bypass = (
                f'/queue simple add name="{bypass_name}" '
                f'target="" max-limit=1G/1G priority=1/1 queue=default/default '
                f'comment="BWM Bypass Priority Group"'
            )
            await exec_cmd_func(cmd_bypass)
            actions.append(f"Antrean bypass '{bypass_name}' dibuat")

        # 2. Create Parent QoS Queue
        if not status["parent"]:
            cmd_parent = (
                f'/queue simple add name="{parent_name}" '
                f'target="{target_subnet}" max-limit={max_limit} priority=8/8 '
                f'queue=default/default comment="BWM Parent Traffic Shaper"'
            )
            await exec_cmd_func(cmd_parent)
            actions.append(f"Antrean induk '{parent_name}' dibuat")

        if actions:
            return True, f"Inisialisasi berhasil: {', '.join(actions)}."
        return True, "Struktur antrean BWM sudah lengkap dan siap digunakan."
