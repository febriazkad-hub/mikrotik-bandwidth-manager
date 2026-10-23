import os
import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger("config")

class MikroTikConfig(BaseModel):
    host: str = "192.168.88.1"
    port: int = 22
    username: str = "admin"
    password: str = ""
    timeout: float = 5.0
    wan_interface: str = "ether1"
    lan_bridge: str = "bridge"
    full_speed_queue: str = "BWM-BYPASS-GROUP"
    default_limit_queue: str = "BWM-DEFAULT-PCQ"

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5678
    admin_pin: str = ""
    debug: bool = False

class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    allowed_chat_ids: list = []
    notify_new_devices: bool = True
    notify_wan_failover: bool = True

class AppConfig(BaseModel):
    mikrotik: MikroTikConfig = MikroTikConfig()
    server: ServerConfig = ServerConfig()
    telegram: TelegramConfig = TelegramConfig()
    db_path: str = "data/mikrotik_manager.db"
    is_configured: bool = False

def load_config() -> AppConfig:
    """
    Load configuration with cascading priority:
    1. Environment variables
    2. config.json (if present)
    3. Factory Defaults (192.168.88.1:22)
    """
    cfg = AppConfig()

    # 1. Check if config.json exists
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "mikrotik" in data:
                    m = data["mikrotik"]
                    cfg.mikrotik.host = m.get("host", cfg.mikrotik.host)
                    cfg.mikrotik.port = int(m.get("port", cfg.mikrotik.port))
                    cfg.mikrotik.username = m.get("username", cfg.mikrotik.username)
                    cfg.mikrotik.password = m.get("password", cfg.mikrotik.password)
                    cfg.mikrotik.timeout = float(m.get("timeout", cfg.mikrotik.timeout))
                if "bandwidth_defaults" in data:
                    bd = data["bandwidth_defaults"]
                    cfg.mikrotik.full_speed_queue = bd.get("full_speed_queue", cfg.mikrotik.full_speed_queue)
                    cfg.mikrotik.default_limit_queue = bd.get("default_limit_queue", cfg.mikrotik.default_limit_queue)
                    cfg.mikrotik.wan_interface = bd.get("wan_interface_primary", cfg.mikrotik.wan_interface)
                    cfg.mikrotik.lan_bridge = bd.get("lan_bridge", cfg.mikrotik.lan_bridge)
                if "server" in data:
                    s = data["server"]
                    cfg.server.host = s.get("host", cfg.server.host)
                    cfg.server.port = int(s.get("port", cfg.server.port))
                    cfg.server.admin_pin = s.get("admin_pin", cfg.server.admin_pin)
                    cfg.server.debug = bool(s.get("debug", cfg.server.debug))
                if "telegram" in data:
                    t = data["telegram"]
                    cfg.telegram.enabled = bool(t.get("enabled", cfg.telegram.enabled))
                    cfg.telegram.bot_token = t.get("bot_token", cfg.telegram.bot_token)
                    cfg.telegram.allowed_chat_ids = t.get("allowed_chat_ids", cfg.telegram.allowed_chat_ids)
                if "database" in data:
                    cfg.db_path = data["database"].get("db_path", cfg.db_path)
                cfg.is_configured = True
        except Exception as e:
            logger.warning(f"Could not parse config.json: {e}")

    # 2. Environment variable overrides (highest priority)
    env_host = os.getenv("MIKROTIK_HOST")
    if env_host:
        cfg.mikrotik.host = env_host
        cfg.is_configured = True
    if os.getenv("MIKROTIK_PORT"):
        try:
            cfg.mikrotik.port = int(os.getenv("MIKROTIK_PORT"))
        except ValueError:
            pass
    if os.getenv("MIKROTIK_USER"):
        cfg.mikrotik.username = os.getenv("MIKROTIK_USER")
    if os.getenv("MIKROTIK_PASS") is not None:
        cfg.mikrotik.password = os.getenv("MIKROTIK_PASS")
    if os.getenv("WAN_INTERFACE"):
        cfg.mikrotik.wan_interface = os.getenv("WAN_INTERFACE")
    if os.getenv("LAN_BRIDGE"):
        cfg.mikrotik.lan_bridge = os.getenv("LAN_BRIDGE")
    if os.getenv("FULL_SPEED_QUEUE"):
        cfg.mikrotik.full_speed_queue = os.getenv("FULL_SPEED_QUEUE")
    if os.getenv("DEFAULT_LIMIT_QUEUE"):
        cfg.mikrotik.default_limit_queue = os.getenv("DEFAULT_LIMIT_QUEUE")

    if os.getenv("WEB_PORT"):
        try:
            cfg.server.port = int(os.getenv("WEB_PORT"))
        except ValueError:
            pass
    if os.getenv("ADMIN_PIN"):
        cfg.server.admin_pin = os.getenv("ADMIN_PIN")

    if os.getenv("TELEGRAM_BOT_TOKEN"):
        cfg.telegram.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        cfg.telegram.enabled = True
    if os.getenv("TELEGRAM_ALLOWED_CHAT_ID"):
        cfg.telegram.allowed_chat_ids = [os.getenv("TELEGRAM_ALLOWED_CHAT_ID")]

    return cfg

app_config = load_config()
