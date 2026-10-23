import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import db_instance
from app.mikrotik_engine import engine_instance

logger = logging.getLogger("scheduler_engine")

class SchedulerEngine:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.known_macs = set()
        self._bot_notifier = None

    def set_bot_notifier(self, notifier_func):
        self._bot_notifier = notifier_func

    async def start(self):
        # Schedule evaluation every 60 seconds
        self.scheduler.add_job(self._evaluate_schedules, 'interval', seconds=60, id='eval_schedules')
        # Schedule device discovery & alert check every 30 seconds
        self.scheduler.add_job(self._check_new_devices, 'interval', seconds=30, id='check_devices')
        self.scheduler.start()
        logger.info("Scheduler Engine started successfully")

    async def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def _evaluate_schedules(self):
        try:
            schedules = await db_instance.get_schedules()
            if not schedules:
                return

            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_day = str(now.weekday())  # 0=Monday, 6=Sunday

            for s in schedules:
                if not s.get("is_enabled"):
                    continue

                days = s.get("days_of_week", "").split(",")
                if current_day not in days:
                    continue

                start = s.get("start_time")
                end = s.get("end_time")
                ip = s.get("device_ip")
                action = s.get("action_mode")
                up = s.get("upload_limit")
                down = s.get("download_limit")

                if not ip or not start or not end:
                    continue

                # Determine if now is within [start, end]
                is_in_range = False
                if start <= end:
                    is_in_range = start <= current_time <= end
                else:
                    # Overnight schedule (e.g. 22:00 - 06:00)
                    is_in_range = current_time >= start or current_time <= end

                if is_in_range:
                    logger.info(f"Applying schedule '{s.get('name')}' for {ip} -> {action}")
                    await engine_instance.set_device_speed(
                        ip=ip,
                        mode=action,
                        upload_limit=up,
                        download_limit=down,
                        mac=s.get("device_mac"),
                        source="schedule"
                    )
        except Exception as e:
            logger.error(f"Error evaluating schedules: {e}")

    async def _check_new_devices(self):
        try:
            devices = await engine_instance.get_all_devices()
            current_macs = {d.mac for d in devices if d.mac}

            if not self.known_macs:
                self.known_macs = current_macs
                return

            new_macs = current_macs - self.known_macs
            if new_macs:
                for d in devices:
                    if d.mac in new_macs:
                        logger.info(f"New device detected: {d.alias_name} ({d.ip}, {d.mac})")
                        await db_instance.log_action("NEW_DEVICE_DETECTED", d.ip, d.mac, f"Perangkat baru terdeteksi: {d.alias_name} ({d.vendor})", "system")
                        if self._bot_notifier:
                            await self._bot_notifier(
                                f"🔔 *Perangkat Baru Terdeteksi!*\n\n"
                                f"• *Nama/Host*: `{d.alias_name}`\n"
                                f"• *IP Address*: `{d.ip}`\n"
                                f"• *MAC*: `{d.mac}`\n"
                                f"• *Vendor*: {d.vendor}\n"
                                f"• *Status*: Terhubung ke Wi-Fi"
                            )
                self.known_macs.update(new_macs)
        except Exception as e:
            logger.debug(f"Error checking new devices: {e}")

scheduler_instance = SchedulerEngine()
