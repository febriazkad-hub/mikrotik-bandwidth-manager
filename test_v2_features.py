import asyncio
import sys
import os
import requests
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5678"

def test_rest_endpoints():
    print("=== TEST 1: REST API ENDPOINTS VERIFICATION ===")
    
    # 1. Health
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"1. /api/health: {r.status_code} -> {r.json()}")
    assert r.status_code == 200

    # 2. Stats
    r = requests.get(f"{BASE_URL}/api/stats")
    stats = r.json()
    print(f"2. /api/stats: {r.status_code} -> Board={stats['board_name']}, DL={stats['total_download_str']}, UL={stats['total_upload_str']}")
    assert r.status_code == 200

    # 3. WOL (Wake-on-LAN)
    r = requests.post(f"{BASE_URL}/api/devices/192.168.77.29/wol", json={"mac": "40:16:7E:23:A0:8A"})
    print(f"3. /api/devices/.../wol: {r.status_code} -> {r.json()}")
    assert r.status_code == 200
    assert r.json()["success"] == True

    # 4. Diagnostic Ping
    r = requests.post(f"{BASE_URL}/api/tools/ping", json={"target": "8.8.8.8", "count": 2})
    print(f"4. /api/tools/ping: {r.status_code} -> Output preview: {r.json().get('output', '')[:80]}...")
    assert r.status_code == 200

    # 5. Diagnostic DNS Lookup
    r = requests.post(f"{BASE_URL}/api/tools/dns", json={"domain": "google.com"})
    print(f"5. /api/tools/dns: {r.status_code} -> Output: {r.json().get('output', '').strip()}")
    assert r.status_code == 200

    # 6. Diagnostic ARP Table
    r = requests.get(f"{BASE_URL}/api/tools/arp")
    arp_entries = r.json().get("data", [])
    print(f"6. /api/tools/arp: {r.status_code} -> Total entries: {len(arp_entries)}")
    assert r.status_code == 200
    assert len(arp_entries) > 0

    # 7. Firewall Rules
    r = requests.get(f"{BASE_URL}/api/firewall")
    fw = r.json().get("data", {})
    print(f"7. /api/firewall: {r.status_code} -> Filter rules count: {len(fw.get('filter', []))}, NAT count: {len(fw.get('nat', []))}")
    assert r.status_code == 200

    # 8. Backup & Export
    r = requests.get(f"{BASE_URL}/api/backup/export", timeout=120)
    backup = r.json()
    print(f"8. /api/backup/export: {r.status_code} -> Config chars: {len(backup.get('config', ''))}, Model: {backup.get('routerboard', {}).get('model')}")
    assert r.status_code == 200
    assert len(backup.get('config', '')) > 500

    # 9. Security Audit
    r = requests.get(f"{BASE_URL}/api/security/audit")
    sec = r.json().get("data", {})
    print(f"9. /api/security/audit: {r.status_code} -> Score: {sec.get('score')}%, Total checks: {len(sec.get('checks', []))}")
    assert r.status_code == 200

    print("[PASSED] All 9 REST API endpoints verified successfully!\n")

async def test_playwright_gui():
    print("=== TEST 2: PLAYWRIGHT WEB GUI & INTERACTIVE TOOLS VERIFICATION ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1366, 'height': 900})
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)

        print("Navigating to http://localhost:5678...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_selector(".device-card", timeout=10000)
        print("Device cards loaded.")

        # 1. Check WOL button presence on PC cards
        wol_buttons = await page.query_selector_all("button:has-text('Wake (WOL)')")
        print(f"Found {len(wol_buttons)} Wake-on-LAN buttons on PC/Server cards.")
        assert len(wol_buttons) >= 2, "Expected at least 2 WOL buttons for PC and Debian server"

        # 2. Test Diagnostic Tools Tab
        print("Switching to Tab: Alat Diagnostik...")
        await page.click("#tab-btn-tools")
        await asyncio.sleep(1)

        # Run Ping in GUI
        print("Executing Ping test via GUI...")
        await page.fill("#tool-ping-target", "1.1.1.1")
        await page.click("#btn-tool-ping")
        # Wait until button is re-enabled (ping finished)
        await page.wait_for_function("() => !document.getElementById('btn-tool-ping').disabled", timeout=15000)
        ping_out = await page.text_content("#tool-ping-output")
        print(f"GUI Ping Output Preview: {ping_out[:80]}...")
        assert "received" in ping_out.lower() or "ms" in ping_out.lower() or "sent" in ping_out.lower()

        # Check ARP table in GUI
        arp_rows = await page.query_selector_all("#arp-tbody tr")
        print(f"GUI ARP table rows rendered: {len(arp_rows)}")
        assert len(arp_rows) > 0

        # 3. Test Firewall Viewer Tab
        print("Switching to Tab: Firewall...")
        await page.click("#tab-btn-firewall")
        await asyncio.sleep(1.5)
        fw_rows = await page.query_selector_all("#firewall-content tr")
        print(f"Firewall filter rows rendered: {len(fw_rows)}")
        assert len(fw_rows) > 0

        # Switch to NAT sub-tab
        await page.click("#fw-subtab-nat")
        await asyncio.sleep(0.5)
        nat_rows = await page.query_selector_all("#firewall-content tr")
        print(f"Firewall NAT rows rendered: {len(nat_rows)}")

        # 4. Test Security & Backup Tab
        print("Switching to Tab: Keamanan & Backup...")
        await page.click("#tab-btn-security")
        await asyncio.sleep(1.5)
        sec_score = await page.text_content("#security-score-val")
        print(f"Security Hardening Score in UI: {sec_score}")
        assert "%" in sec_score

        # Click export preview button
        await page.click("button:has-text('Lihat Script .rsc')")
        await asyncio.sleep(2)
        export_text = await page.text_content("#backup-export-preview")
        print(f"Export preview text length: {len(export_text)} chars")
        assert len(export_text) > 500

        # 5. Test Terminal Modal & xterm.js
        print("Testing In-Browser SSH Terminal Modal...")
        await page.click("button:has-text('Terminal')")
        await asyncio.sleep(1.5)
        modal_term_hidden = await page.eval_on_selector("#modal-terminal", "el => el.classList.contains('hidden')")
        print(f"Terminal Modal opened: {not modal_term_hidden}")
        assert not modal_term_hidden

        # Close terminal
        await page.click("#modal-terminal button:has-text('×')")
        await asyncio.sleep(0.5)

        # 6. Take complete screenshot of new v2 dashboard
        screenshot_path = "C:\\Users\\Administrator\\MikroTik_Bandwidth_Manager\\static\\v2_features_verified.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"[OK] Complete v2 features screenshot saved to {screenshot_path}")

        print("\n=======================================================")
        print("  ALL V2 FEATURES & GUI INTERACTIVE TESTS PASSED (100%)")
        print("=======================================================")

        await browser.close()

if __name__ == "__main__":
    test_rest_endpoints()
    asyncio.run(test_playwright_gui())
