import asyncio
import os
import sys
import requests
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.mikrotik_engine import engine_instance, extract_ips_from_target
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5678"

async def test_bandwidth_limiter_logic():
    print("=== TEST 1: STRICT BANDWIDTH LIMITER & QUEUE LOGIC ===")
    
    test_ip = "192.168.77.24"
    test_mac = "90:DD:5D:49:A5:EB"

    # Step 1: Set to sosmed_2m (2 Mbps)
    print(f"\n1. Setting {test_ip} to 'sosmed_2m' (2 Mbps)...")
    r = requests.post(f"{BASE_URL}/api/devices/{test_ip}/speed", json={"ip": test_ip, "mac": test_mac, "mode": "sosmed_2m"})
    assert r.status_code == 200, f"Failed: {r.text}"
    
    # Verify in MikroTik
    vips = await engine_instance.get_vip_targets()
    print(f"Current VIPs in Rule 0: {vips}")
    assert test_ip not in vips, f"ERROR: {test_ip} is still in PRIORITY-FULL-GROUP!"
    
    q_out = await engine_instance.exec_cmd(f'/queue simple print detail where name="LIMIT-{test_ip}"')
    print(f"Queue LIMIT-{test_ip} details:\n{q_out.strip()}")
    assert "max-limit=2M/2M" in q_out, "ERROR: max-limit is not 2M/2M!"

    # Step 2: Set to blocked (0 Mbps)
    print(f"\n2. Setting {test_ip} to 'blocked' (0 Mbps)...")
    r = requests.post(f"{BASE_URL}/api/devices/{test_ip}/speed", json={"ip": test_ip, "mac": test_mac, "mode": "blocked"})
    assert r.status_code == 200
    
    vips = await engine_instance.get_vip_targets()
    assert test_ip not in vips, f"ERROR: {test_ip} is still in VIP list during blocked mode!"
    q_out = await engine_instance.exec_cmd(f'/queue simple print detail where name="LIMIT-{test_ip}"')
    assert "max-limit=1k/1k" in q_out

    # Step 3: Set back to full (1 Gbps)
    print(f"\n3. Setting {test_ip} to 'full' (1 Gbps Bypass)...")
    r = requests.post(f"{BASE_URL}/api/devices/{test_ip}/speed", json={"ip": test_ip, "mac": test_mac, "mode": "full"})
    assert r.status_code == 200
    
    vips = await engine_instance.get_vip_targets()
    print(f"Current VIPs after full: {vips}")
    assert test_ip in vips, f"ERROR: {test_ip} was NOT added to PRIORITY-FULL-GROUP!"
    check_q = await engine_instance.exec_cmd(f'/queue simple print count-only where name="LIMIT-{test_ip}"')
    assert int(check_q.strip()) == 0, f"ERROR: LIMIT-{test_ip} was not removed!"

    # Step 4: Apply Gaming & Work preset
    print("\n4. Applying 'gaming_work' preset...")
    r = requests.post(f"{BASE_URL}/api/presets/gaming_work/apply")
    assert r.status_code == 200
    
    vips = await engine_instance.get_vip_targets()
    print(f"VIPs in gaming_work: {vips}")
    assert "192.168.77.29" in vips
    assert "192.168.77.16" in vips
    assert test_ip not in vips, f"ERROR: non-VIP {test_ip} should not be in VIP list in gaming_work"

    # Step 5: Test Sanitize Queues
    print("\n5. Running Sanitize Queues check...")
    await engine_instance.sanitize_queues()
    print("[PASSED] Strict bandwidth limiter and queue verification passed 100%!\n")

async def test_playwright_ui_audit():
    print("=== TEST 2: PLAYWRIGHT GUI AUDIT & BUG VERIFICATION ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1366, 'height': 900})
        page = await context.new_page()

        print("Navigating to dashboard...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_selector(".device-card", timeout=10000)

        # 1. Verify live throughput rate badge on device cards
        card_throughput = await page.query_selector_all(".device-card span[title='Live Download']")
        print(f"Found {len(card_throughput)} device cards with live download rate badges.")
        assert len(card_throughput) > 0, "Expected live throughput indicators on device cards"

        # 2. Test Preset button click and highlight persistence
        print("Testing preset highlight persistence...")
        await page.click("#preset-btn-gaming_work")
        await asyncio.sleep(2)
        has_ring = await page.eval_on_selector("#preset-btn-gaming_work", "el => el.classList.contains('ring-2')")
        print(f"Preset button 'Gaming & Work' has sticky ring-2 highlight: {has_ring}")
        assert has_ring, "Expected preset button to retain ring-2 class"

        # Wait for a 5s periodic refresh and verify highlight is still retained
        print("Waiting 6 seconds for periodic auto-refresh...")
        await asyncio.sleep(6)
        has_ring_after_refresh = await page.eval_on_selector("#preset-btn-gaming_work", "el => el.classList.contains('ring-2')")
        print(f"Preset button retained highlight after 6s periodic refresh: {has_ring_after_refresh}")
        assert has_ring_after_refresh, "Preset highlight was wiped by auto-refresh!"

        # 3. Take screenshot of fixed UI
        screenshot_path = "C:\\Users\\Administrator\\MikroTik_Bandwidth_Manager\\static\\limiter_fix_verified.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"[OK] Audit fix screenshot saved to {screenshot_path}")

        print("\n=======================================================")
        print("  ALL STRICT LIMITER & GUI BUG FIXES VERIFIED (100%)")
        print("=======================================================")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_bandwidth_limiter_logic())
    asyncio.run(test_playwright_ui_audit())
