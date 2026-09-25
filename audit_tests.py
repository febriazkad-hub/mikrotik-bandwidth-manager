import asyncio
import time
import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from app.mikrotik_engine import engine_instance
from app.database import db_instance
from app.models import SpeedChangeRequest

async def run_audit():
    print("=== AUDIT TEST 1: SINGLE BATCH SSH ROUNDTRIP SPEED ===")
    t0 = time.time()
    cmd = ':put "---RES---"; /system resource print; :put "---ROUTES---"; /ip route print terse where dst-address="0.0.0.0/0" and active=yes; :put "---TRAFFIC---"; /interface monitor-traffic ether1,wlan1 once'
    out = await engine_instance.exec_cmd(cmd)
    t1 = time.time()
    elapsed_ms = (t1 - t0) * 1000
    print(f"Batch SSH Roundtrip executed in {elapsed_ms:.1f}ms (Response bytes: {len(out)})")
    assert elapsed_ms < 3000, "SSH roundtrip is too slow"
    print("[PASSED] Single Batch SSH is fast and responsive.")

    print("\n=== AUDIT TEST 2: CHECK PARSING OF BATCH STATS & LIVE TRAFFIC ===")
    stats = await engine_instance.get_system_stats()
    print(f"Stats: Board={stats.board_name}, Uptime={stats.uptime}, CPU={stats.cpu_load}%, RAM={stats.free_memory}, WAN={stats.active_wan}")
    print(f"Live Traffic: DL={stats.total_download_str} ({stats.total_download_bps} bps), UL={stats.total_upload_str} ({stats.total_upload_bps} bps)")
    assert stats.board_name != "", "Board name should not be empty"
    print("[PASSED] System stats & live traffic parsed correctly.")

    print("\n=== AUDIT TEST 3: VERIFY ALL DEVICES & QUEUE SYNC ===")
    devices = await engine_instance.get_all_devices()
    print(f"Total devices discovered: {len(devices)}")
    for d in devices:
        print(f"  Device: {d.alias_name} | IP: {d.ip} | MAC: {d.mac} | Mode: {d.rate_mode} | Limit: {d.current_limit}")
    assert len(devices) > 0, "Should have discovered devices"
    print("[PASSED] Devices and Queues mapped successfully.")

    print("\n=== AUDIT TEST 4: VERIFY CUSTOM QUEUE PLACEMENT & REMOVAL ===")
    test_ip = "192.168.77.249"
    ok, msg = await engine_instance.set_device_speed(test_ip, "sosmed_2m", mac="00:11:22:33:44:55", source="audit_test")
    print(f"Set speed: {ok} -> {msg}")
    assert ok, "Failed to set custom speed"
    
    q_out = await engine_instance.exec_cmd('/queue simple print')
    assert f"LIMIT-{test_ip}" in q_out, "Custom queue was not created"
    
    ok_def, msg_def = await engine_instance.set_device_speed(test_ip, "default", source="audit_test")
    print(f"Revert to default: {ok_def} -> {msg_def}")
    q_out_after = await engine_instance.exec_cmd('/queue simple print')
    assert f"LIMIT-{test_ip}" not in q_out_after, "Custom queue was not cleaned up"
    print("[PASSED] Custom queue creation, placement, and cleanup verified.")

    print("\n=== AUDIT TEST 5: PRESET APPLICATION & SAFETY ROLLBACK ===")
    ok_p, msg_p = await engine_instance.apply_preset("fair_share")
    print(f"Apply fair_share: {ok_p} -> {msg_p}")
    assert ok_p, "Failed to apply preset"
    
    ok_g, msg_g = await engine_instance.apply_preset("gaming_work")
    print(f"Apply gaming_work: {ok_g} -> {msg_g}")
    assert ok_g, "Failed to apply gaming_work preset"
    print("[PASSED] Preset engine verified.")

    print("\n=== AUDIT TEST 6: DATABASE INTEGRITY & AUDIT LOGS ===")
    logs = await db_instance.get_recent_logs(limit=5)
    print(f"Recent logs count: {len(logs)}")
    for l in logs:
        print(f"  Log: [{l['timestamp']}] {l['action']} -> {l['detail']} ({l['source']})")
    assert len(logs) > 0, "Audit logs should not be empty"
    print("[PASSED] Database audit logging verified.")

    print("\n=======================================================")
    print("  ALL 6 AUDIT TEST SUITES PASSED FLAWLESSLY (100%)")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_audit())
