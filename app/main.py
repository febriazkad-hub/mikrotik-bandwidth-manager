import os
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    Device, RouterStats, SpeedChangeRequest, DeviceAliasRequest,
    MakeStaticRequest, PresetApplyRequest, ScheduleRule, ApiResponse
)
from app.database import db_instance
from app.mikrotik_engine import engine_instance
from app.scheduler_engine import scheduler_instance
from app.telegram_bot import bot_instance as telegram_instance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# ----------------- WEBSOCKET CONNECTION MANAGER -----------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected (Total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected (Remaining: {len(self.active_connections)})")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        dead_conns = []
        payload = json.dumps(message)
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                dead_conns.append(conn)
        for dc in dead_conns:
            self.disconnect(dc)

ws_manager = ConnectionManager()

# Background broadcast loop for live traffic telemetry
async def traffic_broadcast_loop():
    while True:
        try:
            if ws_manager.active_connections:
                stats = await engine_instance.get_system_stats()
                payload = {
                    "type": "traffic_update",
                    "rx_bps": stats.total_download_bps,
                    "tx_bps": stats.total_upload_bps,
                    "rx_str": stats.total_download_str,
                    "tx_str": stats.total_upload_str,
                    "cpu_load": stats.cpu_load,
                    "free_memory": stats.free_memory,
                    "uptime": stats.uptime,
                    "active_wan": stats.active_wan
                }
                await ws_manager.broadcast(payload)
        except Exception as e:
            logger.debug(f"Broadcast loop tick error: {e}")
        await asyncio.sleep(1.0)

# Background RouterOS log archiver loop (syncs every 60s)
async def log_sync_loop():
    while True:
        try:
            await asyncio.sleep(60.0)
            await engine_instance.sync_routeros_logs()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Log sync background tick error: {e}")

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MikroTik Smart Bandwidth Manager...")
    await db_instance.init_db()
    
    # Start Scheduler
    await scheduler_instance.start()
    
    # Start Telegram Bot if configured
    await telegram_instance.start()
    
    # Sanitize and reconcile queues
    try:
        await engine_instance.sanitize_queues()
    except Exception as e:
        logger.warning(f"Startup queue sanitization: {e}")

    # Initial log sync from MikroTik
    try:
        await engine_instance.sync_routeros_logs()
    except Exception as e:
        logger.warning(f"Startup log sync: {e}")

    # Start background loops
    broadcast_task = asyncio.create_task(traffic_broadcast_loop())
    log_sync_task = asyncio.create_task(log_sync_loop())
    
    yield
    
    logger.info("Shutting down...")
    broadcast_task.cancel()
    log_sync_task.cancel()
    await scheduler_instance.stop()
    await telegram_instance.stop()

app = FastAPI(
    title="MikroTik Smart Bandwidth Manager v2",
    description="Full-Featured Web GUI, Bandwidth QoS, Diagnostics, Terminal, and Automation for RouterOS",
    version="2.0.0",
    lifespan=lifespan
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount Static Files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ----------------- REST API: STATS & HEALTH -----------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.now().isoformat()}

@app.get("/api/stats", response_model=RouterStats)
async def get_stats():
    stats = await engine_instance.get_system_stats()
    devices = await engine_instance.get_all_devices()
    stats.total_devices_all = len(devices)
    stats.total_devices_online = len([d for d in devices if d.status == "bound"])
    return stats

# ----------------- REST API: DEVICES & BANDWIDTH -----------------
@app.get("/api/devices", response_model=List[Device])
async def get_devices():
    return await engine_instance.get_all_devices()

@app.post("/api/devices/{ip}/speed", response_model=ApiResponse)
async def set_speed(ip: str, req: SpeedChangeRequest):
    ok, msg = await engine_instance.set_device_speed(
        ip=ip,
        mode=req.mode,
        upload_limit=req.upload_limit,
        download_limit=req.download_limit,
        priority=req.priority or 8,
        mac=req.mac,
        comment=req.comment,
        source="web"
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return ApiResponse(success=True, message=msg)

@app.post("/api/devices/{ip}/alias", response_model=ApiResponse)
async def set_alias(ip: str, req: DeviceAliasRequest):
    await db_instance.upsert_device_alias(
        mac=req.mac,
        ip=ip,
        alias_name=req.alias_name,
        device_type=req.device_type or "phone",
        group_name=req.group_name or "Default",
        notes=req.notes or ""
    )

    ros_ok, ros_msg = await engine_instance.update_dhcp_lease_comment(ip, req.mac, req.alias_name)
    detail = f"Mengubah alias '{req.alias_name}' ({req.device_type})"
    if ros_ok:
        detail += " + sinkron ke comment DHCP MikroTik"
    else:
        detail += f"; sinkron RouterOS dilewati/gagal: {ros_msg}"
    await db_instance.log_action("SET_ALIAS", ip, req.mac, detail)

    if ros_ok:
        return ApiResponse(success=True, message=f"Nama alias '{req.alias_name}' berhasil disimpan dan disinkronkan ke MikroTik.")
    return ApiResponse(success=True, message=f"Nama alias '{req.alias_name}' berhasil disimpan lokal. Catatan: {ros_msg}")

@app.post("/api/devices/{ip}/static", response_model=ApiResponse)
async def make_static(ip: str, req: MakeStaticRequest):
    ok, msg = await engine_instance.make_static_lease(ip=ip, mac=req.mac, comment=req.comment)
    return ApiResponse(success=ok, message=msg)

# ----------------- REST API: WAKE-ON-LAN -----------------
@app.post("/api/devices/{ip}/wol", response_model=ApiResponse)
async def send_wol_endpoint(ip: str, req: Request):
    body = await req.json()
    mac = body.get("mac", "")
    if not mac:
        raise HTTPException(status_code=400, detail="MAC address is required for WOL")
    ok, msg = await engine_instance.send_wol(mac)
    return ApiResponse(success=ok, message=msg)

# ----------------- REST API: PRESETS -----------------
@app.get("/api/presets")
async def get_presets():
    return await db_instance.get_presets()

@app.post("/api/presets/{preset_id}/apply", response_model=ApiResponse)
async def apply_preset(preset_id: str):
    ok, msg = await engine_instance.apply_preset(preset_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return ApiResponse(success=True, message=msg)

# ----------------- REST API: SCHEDULES -----------------
@app.get("/api/schedules")
async def get_schedules():
    return await db_instance.get_schedules()

@app.post("/api/schedules", response_model=ApiResponse)
async def add_schedule(req: ScheduleRule):
    sched_id = await db_instance.add_schedule(req.model_dump())
    await db_instance.log_action("ADD_SCHEDULE", req.device_ip, req.device_mac or "", f"Menambahkan jadwal '{req.name}' ({req.start_time}-{req.end_time})")
    return ApiResponse(success=True, message=f"Jadwal '{req.name}' berhasil ditambahkan.", data={"id": sched_id})

@app.delete("/api/schedules/{schedule_id}", response_model=ApiResponse)
async def delete_schedule(schedule_id: int):
    await db_instance.delete_schedule(schedule_id)
    await db_instance.log_action("DELETE_SCHEDULE", "", "", f"Menghapus jadwal ID {schedule_id}")
    return ApiResponse(success=True, message=f"Jadwal #{schedule_id} berhasil dihapus.")

@app.post("/api/schedules/{schedule_id}/toggle", response_model=ApiResponse)
async def toggle_schedule(schedule_id: int, req: Dict[str, bool]):
    is_enabled = req.get("is_enabled", True)
    await db_instance.toggle_schedule(schedule_id, is_enabled)
    status_txt = "diaktifkan" if is_enabled else "dinonaktifkan"
    return ApiResponse(success=True, message=f"Jadwal #{schedule_id} berhasil {status_txt}.")

# ----------------- REST API: AUDIT LOGS & ROUTEROS LOGS -----------------
@app.get("/api/logs")
async def get_logs():
    return await db_instance.get_recent_logs(limit=50)

@app.get("/api/routeros/logs")
async def get_routeros_logs(
    limit: int = 100,
    offset: int = 0,
    severity: Optional[str] = None,
    topic: Optional[str] = None,
    search: Optional[str] = None,
    sync: bool = False
):
    if sync:
        await engine_instance.sync_routeros_logs()
    logs = await db_instance.get_routeros_logs(
        limit=limit,
        offset=offset,
        severity=severity,
        topic=topic,
        search=search
    )
    total_count = await db_instance.get_routeros_logs_count()
    return {"success": True, "total": total_count, "count": len(logs), "data": logs}

@app.post("/api/routeros/logs/sync")
async def trigger_sync_routeros_logs():
    inserted, msg = await engine_instance.sync_routeros_logs()
    return {"success": True, "inserted": inserted, "message": msg}

@app.delete("/api/routeros/logs")
async def clear_routeros_logs():
    await db_instance.clear_routeros_logs()
    return {"success": True, "message": "Semua riwayat log RouterOS lokal berhasil dibersihkan."}

# ----------------- REST API: DIAGNOSTIC TOOLS -----------------
@app.post("/api/tools/ping")
async def tool_ping(req: Request):
    body = await req.json()
    target = body.get("target", "8.8.8.8")
    count = int(body.get("count", 4))
    output = await engine_instance.run_ping(target, count)
    return {"success": True, "target": target, "output": output}

@app.post("/api/tools/traceroute")
async def tool_traceroute(req: Request):
    body = await req.json()
    target = body.get("target", "8.8.8.8")
    output = await engine_instance.run_traceroute(target)
    return {"success": True, "target": target, "output": output}

@app.post("/api/tools/dns")
async def tool_dns(req: Request):
    body = await req.json()
    domain = body.get("domain", "google.com")
    output = await engine_instance.run_dns_lookup(domain)
    return {"success": True, "domain": domain, "output": output}

@app.get("/api/tools/arp")
async def tool_arp():
    entries = await engine_instance.get_arp_table()
    return {"success": True, "data": entries}

# ----------------- REST API: FIREWALL -----------------
@app.get("/api/firewall")
async def get_firewall():
    rules = await engine_instance.get_firewall_rules()
    return {"success": True, "data": rules}

# ----------------- REST API: BACKUP & EXPORT -----------------
@app.get("/api/backup/export")
async def get_backup_export():
    config = await engine_instance.export_config()
    rb_info = await engine_instance.get_routerboard_info()
    return {"success": True, "config": config, "routerboard": rb_info, "timestamp": datetime.now().isoformat()}

@app.get("/api/backup/download")
async def download_backup():
    config = await engine_instance.export_config()
    filename = f"mikrotik_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.rsc"
    return Response(
        content=config,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ----------------- REST API: SECURITY AUDIT -----------------
@app.get("/api/security/audit")
async def get_security_audit():
    result = await engine_instance.run_security_audit()
    return {"success": True, "data": result}

# ----------------- REST API: ROUTER POWER ACTIONS -----------------
@app.post("/api/router/reboot", response_model=ApiResponse)
async def reboot_router():
    ok, msg = await engine_instance.reboot_router()
    return ApiResponse(success=ok, message=msg)

# ----------------- REST API: FASTTRACK CONTROL -----------------
@app.get("/api/fasttrack/status")
async def get_fasttrack_status():
    from app.firewall_helper import FirewallHelper
    status = await FirewallHelper.check_fasttrack_status(engine_instance.exec_cmd)
    return {"success": True, "data": status}

@app.post("/api/fasttrack/toggle", response_model=ApiResponse)
async def toggle_fasttrack(req: Request):
    from app.firewall_helper import FirewallHelper
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    enable = body.get("enable", False)
    if enable:
        ok, msg = await FirewallHelper.restore_fasttrack(engine_instance.exec_cmd)
    else:
        ok, msg = await FirewallHelper.disable_fasttrack_safe(engine_instance.exec_cmd)
    return ApiResponse(success=ok, message=msg)

# ----------------- REST API: CLEAN DETACH / SAFE UNINSTALL -----------------
@app.post("/api/maintenance/clean-detach", response_model=ApiResponse)
async def clean_detach():
    from app.uninstall_helper import UninstallHelper
    from app.config import get_settings
    settings = get_settings()
    ok, msg = await UninstallHelper.clean_detach(
        engine_instance.exec_cmd,
        parent_name=settings.bypass_queue_name,
        bypass_name=settings.bypass_queue_name
    )
    return ApiResponse(success=ok, message=msg)

# ----------------- REST API: FIRST-RUN SETUP & DISCOVERY -----------------
@app.get("/api/setup/status")
async def get_setup_status():
    from app.config import get_settings
    settings = get_settings()
    configured = bool(settings.router_host and settings.router_user)
    return {
        "success": True,
        "configured": configured,
        "host": settings.router_host,
        "port": settings.router_port,
        "user": settings.router_user,
        "wan_interface": settings.wan_interface,
        "lan_bridge": settings.lan_bridge
    }

@app.post("/api/setup/probe")
async def probe_router(req: Request):
    from app.discovery import RouterDiscovery
    body = await req.json()
    host = body.get("host", "192.168.88.1")
    port = int(body.get("port", 22))
    user = body.get("user", "admin")
    password = body.get("password", "")

    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=5.0,
                look_for_keys=False,
                allow_agent=False
            )
        )
    except Exception as e:
        return {"success": False, "error": f"Gagal terhubung ke {host}:{port} ({str(e)})"}

    try:
        def _exec(cmd):
            _, stdout, _ = client.exec_command(cmd, timeout=5.0)
            return stdout.read().decode("utf-8", errors="replace")

        res_out = await asyncio.get_event_loop().run_in_executor(None, _exec, "/system resource print")
        route_out = await asyncio.get_event_loop().run_in_executor(None, _exec, '/ip route print terse where dst-address="0.0.0.0/0" and active=yes')
        dhcp_c_out = await asyncio.get_event_loop().run_in_executor(None, _exec, "/ip dhcp-client print terse")
        bridge_out = await asyncio.get_event_loop().run_in_executor(None, _exec, "/interface bridge print terse")
        ip_addr_out = await asyncio.get_event_loop().run_in_executor(None, _exec, "/ip address print terse")
        ft_out = await asyncio.get_event_loop().run_in_executor(None, _exec, "/ip firewall filter print terse where action=fasttrack-connection")

        ros_info = RouterDiscovery.parse_version_and_arch(res_out)
        wan_iface = RouterDiscovery.detect_wan_interface(route_out, dhcp_c_out)
        lan_bridge = RouterDiscovery.detect_lan_bridge(bridge_out, ip_addr_out)

        ft_status = {
            "exists": bool(ft_out.strip()),
            "is_active": bool(ft_out.strip() and "disabled=yes" not in ft_out)
        }

        return {
            "success": True,
            "host": host,
            "port": port,
            "model": ros_info.get("board_name"),
            "version": ros_info.get("version"),
            "major_version": ros_info.get("major_version"),
            "architecture": ros_info.get("architecture"),
            "wan_interface": wan_iface,
            "lan_bridge": lan_bridge,
            "fasttrack": ft_status
        }
    finally:
        client.close()

@app.post("/api/setup/apply", response_model=ApiResponse)
async def apply_setup(req: Request):
    from app.queue_provisioner import QueueProvisioner
    from app.firewall_helper import FirewallHelper
    body = await req.json()
    host = body.get("host", "192.168.88.1")
    port = int(body.get("port", 22))
    user = body.get("user", "admin")
    password = body.get("password", "")
    wan = body.get("wan_interface", "ether1")
    lan = body.get("lan_bridge", "bridge")
    disable_fasttrack = body.get("disable_fasttrack", True)

    await db_instance.set_setting("router_host", host)
    await db_instance.set_setting("router_port", str(port))
    await db_instance.set_setting("router_user", user)
    await db_instance.set_setting("router_password", password)
    await db_instance.set_setting("wan_interface", wan)
    await db_instance.set_setting("lan_bridge", lan)
    await db_instance.set_setting("setup_completed", "true")

    engine_instance.host = host
    engine_instance.port = port
    engine_instance.user = user
    engine_instance.password = password
    engine_instance.wan_interface = wan
    engine_instance.lan_bridge = lan
    engine_instance.close_client()

    await QueueProvisioner.provision_baseline(engine_instance.exec_cmd)

    if disable_fasttrack:
        await FirewallHelper.disable_fasttrack_safe(engine_instance.exec_cmd)

    return ApiResponse(success=True, message=f"Setup berhasil! Terhubung ke {host} via {lan}.")

# ----------------- REST API: GENERAL WAKE-ON-LAN -----------------
@app.post("/api/wol", response_model=ApiResponse)
async def send_general_wol(req: Request):
    body = await req.json()
    mac = body.get("mac", "")
    interface = body.get("interface")
    if not mac:
        raise HTTPException(status_code=400, detail="MAC address is required")
    ok, msg = await engine_instance.send_wol(mac, interface)
    return ApiResponse(success=ok, message=msg)

# ----------------- WEBSOCKET: LIVE TRAFFIC STREAM -----------------
@app.websocket("/ws/traffic")
async def websocket_traffic(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# ----------------- WEBSOCKET: IN-BROWSER SSH TERMINAL -----------------
@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()
    client = None
    channel = None
    read_task = None
    try:
        client = await engine_instance.get_client()
        transport = client.get_transport()
        channel = transport.open_session()
        channel.get_pty(term="xterm", width=120, height=35)
        channel.invoke_shell()

        async def read_from_ssh():
            loop = asyncio.get_event_loop()
            while not channel.closed:
                if channel.recv_ready():
                    data = await loop.run_in_executor(None, channel.recv, 4096)
                    if data:
                        await websocket.send_text(data.decode("utf-8", errors="replace"))
                await asyncio.sleep(0.02)

        read_task = asyncio.create_task(read_from_ssh())

        while True:
            data = await websocket.receive_text()
            channel.send(data)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
    finally:
        if read_task:
            read_task.cancel()
        if channel and not channel.closed:
            channel.close()

# ----------------- FRONTEND SPA ROOT -----------------
@app.get("/", response_class=FileResponse)
async def index():
    index_file = os.path.join(static_dir, "index.html")
    return FileResponse(index_file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5678, reload=False)
