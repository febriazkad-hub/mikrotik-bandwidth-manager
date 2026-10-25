import os
import json
import aiosqlite
from typing import List, Dict, Optional, Any
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mikrotik_manager.db")

class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS device_metadata (
                    mac TEXT PRIMARY KEY,
                    last_ip TEXT,
                    alias_name TEXT,
                    device_type TEXT DEFAULT 'phone',
                    group_name TEXT DEFAULT 'Default',
                    notes TEXT,
                    preferred_mode TEXT DEFAULT 'default',
                    custom_up TEXT,
                    custom_down TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS bandwidth_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    icon TEXT,
                    rules_json TEXT,
                    is_active INTEGER DEFAULT 0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_ip TEXT,
                    device_mac TEXT,
                    device_alias TEXT,
                    name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    action_mode TEXT,
                    upload_limit TEXT,
                    download_limit TEXT,
                    days_of_week TEXT,
                    is_enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    target_ip TEXT,
                    target_mac TEXT,
                    detail TEXT,
                    source TEXT DEFAULT 'web'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS traffic_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rx_bps INTEGER,
                    tx_bps INTEGER,
                    cpu_load INTEGER
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS routeros_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    log_time TEXT,
                    topics TEXT,
                    message TEXT,
                    severity TEXT DEFAULT 'info',
                    source TEXT DEFAULT 'routeros'
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ros_logs_id ON routeros_logs (id DESC)
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()

            # Seed default known devices with clean open-source baseline
            await self._seed_default_devices(db)
            # Seed default presets if empty
            await self._seed_default_presets(db)

    async def _seed_default_devices(self, db):
        # Open-source clean release: devices are discovered dynamically from RouterOS DHCP leases
        pass

    async def _seed_default_presets(self, db):
        presets = [
            ("fair_share", "Family Balanced (4 Mbps)", "Semua perangkat dibagi adil rata 4M via PCQ", "fa-scale-balanced", json.dumps({"mode": "fair_share"})),
            ("gaming_work", "Gaming & Work Priority", "Perangkat VIP Full Speed, lainnya dibatasi 2M", "fa-gamepad", json.dumps({"mode": "gaming_work", "vip_ips": []})),
            ("all_unrestricted", "All Full Speed", "Semua perangkat bebas tanpa batasan bandwidth", "fa-bolt", json.dumps({"mode": "all_unrestricted"})),
            ("night_mode", "Night Saver Mode", "Hemat bandwidth malam hari untuk perangkat hiburan/tamu", "fa-moon", json.dumps({"mode": "night_mode"}))
        ]
        for pid, name, desc, icon, rules in presets:
            await db.execute("""
                INSERT OR IGNORE INTO bandwidth_presets (id, name, description, icon, rules_json)
                VALUES (?, ?, ?, ?, ?)
            """, (pid, name, desc, icon, rules))
        await db.commit()

    async def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM device_metadata")
            rows = await cursor.fetchall()
            result = {}
            for r in rows:
                result[r["mac"].upper()] = dict(r)
            return result

    async def upsert_device_alias(self, mac: str, ip: str, alias_name: str, device_type: str = "phone", group_name: str = "Default", notes: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO device_metadata (mac, last_ip, alias_name, device_type, group_name, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(mac) DO UPDATE SET
                    last_ip=excluded.last_ip,
                    alias_name=excluded.alias_name,
                    device_type=excluded.device_type,
                    group_name=excluded.group_name,
                    notes=excluded.notes,
                    updated_at=CURRENT_TIMESTAMP
            """, (mac.upper(), ip, alias_name, device_type, group_name, notes))
            await db.commit()

    async def log_action(self, action: str, target_ip: str, target_mac: str, detail: str, source: str = "web"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO audit_logs (action, target_ip, target_mac, detail, source)
                VALUES (?, ?, ?, ?, ?)
            """, (action, target_ip, target_mac, detail, source))
            await db.commit()

    async def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_presets(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM bandwidth_presets")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_schedules(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM schedules ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def add_schedule(self, schedule: Dict[str, Any]) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO schedules (device_ip, device_mac, device_alias, name, start_time, end_time, action_mode, upload_limit, download_limit, days_of_week, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                schedule.get("device_ip"),
                schedule.get("device_mac"),
                schedule.get("device_alias"),
                schedule.get("name"),
                schedule.get("start_time"),
                schedule.get("end_time"),
                schedule.get("action_mode"),
                schedule.get("upload_limit"),
                schedule.get("download_limit"),
                schedule.get("days_of_week", "0,1,2,3,4,5,6"),
                1 if schedule.get("is_enabled", True) else 0
            ))
            await db.commit()
            return cursor.lastrowid

    async def delete_schedule(self, schedule_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            await db.commit()

    async def toggle_schedule(self, schedule_id: int, is_enabled: bool):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE schedules SET is_enabled = ? WHERE id = ?", (1 if is_enabled else 0, schedule_id))
            await db.commit()

    async def record_traffic_point(self, rx_bps: int, tx_bps: int, cpu_load: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO traffic_history (rx_bps, tx_bps, cpu_load)
                VALUES (?, ?, ?)
            """, (rx_bps, tx_bps, cpu_load))
            await db.execute("DELETE FROM traffic_history WHERE timestamp <= datetime('now', '-1 day')")
            await db.commit()

    async def insert_routeros_logs(self, logs: List[Dict[str, Any]]) -> int:
        if not logs:
            return 0
        inserted = 0
        async with aiosqlite.connect(self.db_path) as db:
            # ⚡ Bolt: Batch fetch recent logs to avoid N+1 queries during de-duplication
            cursor = await db.execute("SELECT log_time, topics, message FROM routeros_logs ORDER BY id DESC LIMIT 2000")
            recent_rows = await cursor.fetchall()
            existing_logs = {(row[0], row[1], row[2]) for row in recent_rows}

            insert_data = []
            for log in logs:
                log_time = log.get("time", "")
                topics = log.get("topics", "")
                message = log.get("message", "")
                severity = log.get("severity", "info")
                source = log.get("source", "routeros")

                log_key = (log_time, topics, message)
                if log_key not in existing_logs:
                    insert_data.append((log_time, topics, message, severity, source))
                    existing_logs.add(log_key)

            if insert_data:
                # ⚡ Bolt: Use executemany for batch insertion
                await db.executemany("""
                    INSERT INTO routeros_logs (log_time, topics, message, severity, source)
                    VALUES (?, ?, ?, ?, ?)
                """, insert_data)
                inserted = len(insert_data)

            if inserted > 0:
                # Keep maximum 5,000 logs in local SQLite storage
                await db.execute("""
                    DELETE FROM routeros_logs WHERE id NOT IN (
                        SELECT id FROM routeros_logs ORDER BY id DESC LIMIT 5000
                    )
                """)
                await db.commit()
        return inserted

    async def get_routeros_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: Optional[str] = None,
        topic: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM routeros_logs WHERE 1=1"
            params = []

            if severity and severity != "all":
                if severity == "error":
                    query += " AND severity IN ('error', 'critical')"
                else:
                    query += " AND severity = ?"
                    params.append(severity)

            if topic and topic != "all":
                query += " AND topics LIKE ?"
                params.append(f"%{topic}%")

            if search:
                query += " AND (message LIKE ? OR topics LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_routeros_logs_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM routeros_logs")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def clear_routeros_logs(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM routeros_logs")
            await db.commit()

    async def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (key, value))
            await db.commit()

db_instance = Database()
