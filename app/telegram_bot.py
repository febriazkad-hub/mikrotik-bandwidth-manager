import os
import asyncio
import logging
from typing import Optional, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from app.mikrotik_engine import engine_instance
from app.database import db_instance

logger = logging.getLogger("telegram_bot")

class TelegramBotManager:
    def __init__(self, token: Optional[str] = None, allowed_chats: Optional[List[int]] = None):
        self.token = token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
        if allowed_chats is not None:
            self.allowed_chats = allowed_chats
        else:
            env_chats = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "")
            self.allowed_chats = [int(c.strip()) for c in env_chats.split(",") if c.strip().isdigit()]
        self.app = None
        self._task = None

    def is_authorized(self, chat_id: int) -> bool:
        if not self.allowed_chats:
            return True
        return chat_id in self.allowed_chats

    async def start(self):
        if not self.token or self.token.strip() == "":
            logger.info("Telegram Bot Token is not configured. Telegram bot disabled.")
            return

        try:
            self.app = ApplicationBuilder().token(self.token).build()

            self.app.add_handler(CommandHandler("start", self._cmd_start))
            self.app.add_handler(CommandHandler("help", self._cmd_help))
            self.app.add_handler(CommandHandler("status", self._cmd_status))
            self.app.add_handler(CommandHandler("devices", self._cmd_devices))
            self.app.add_handler(CommandHandler("full", self._cmd_full))
            self.app.add_handler(CommandHandler("limit", self._cmd_limit))
            self.app.add_handler(CommandHandler("preset", self._cmd_preset))
            self.app.add_handler(CallbackQueryHandler(self._handle_callback))

            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            logger.info("Telegram Bot started and polling successfully")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")

    async def stop(self):
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def send_alert(self, text: str):
        if not self.app or not self.allowed_chats:
            return
        for cid in self.allowed_chats:
            try:
                await self.app.bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send telegram message to {cid}: {e}")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ Anda tidak memiliki akses ke bot ini.")
            return
        msg = (
            "👋 *Selamat datang di MikroTik Bandwidth Manager Bot!*\n\n"
            "Gunakan bot ini untuk mengontrol bandwidth seluruh perangkat di rumah dari mana saja.\n\n"
            "📌 *Perintah Cepat:*\n"
            "• `/status` - Cek performa router, CPU, & lalu lintas\n"
            "• `/devices` - Daftar perangkat online & tombol kontrol kecepatan 1-klik\n"
            "• `/full <IP>` - Set perangkat ke Full Speed (1 Gbps)\n"
            "• `/limit <IP> <kecepatan>` - Set limit (contoh: `/limit 192.168.88.50 2M`)\n"
            "• `/preset` - Pilih mode jaringan global (Gaming, Family, All Full)"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._cmd_start(update, context)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_chat.id):
            return
        try:
            stats = await engine_instance.get_system_stats()
            devices = await engine_instance.get_all_devices()
            online_count = sum(1 for d in devices if d.status == "bound")

            msg = (
                f"📊 *STATUS MIKROTIK ROUTEROS*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• *Model*: `{stats.board_name}` (`{stats.version}`)\n"
                f"• *Uptime*: `{stats.uptime}`\n"
                f"• *Beban CPU*: `{stats.cpu_load}%`\n"
                f"• *RAM Bebas*: `{stats.free_memory}` / `{stats.total_memory}`\n"
                f"• *Storage Bebas*: `{stats.free_hdd}` / `{stats.total_hdd}`\n"
                f"• *Jalur Internet*: `{stats.active_wan}`\n\n"
                f"⚡ *Lalu Lintas Saat Ini:*\n"
                f"• ⬇️ Download: `{stats.total_download_str}`\n"
                f"• ⬆️ Upload: `{stats.total_upload_str}`\n"
                f"• 📱 Perangkat Terhubung: `{online_count}` aktif"
            )
            keyboard = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="btn_refresh_status")]]
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal mengambil status: {e}")

    async def _cmd_devices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_chat.id):
            return
        try:
            devices = await engine_instance.get_all_devices()
            online_devs = [d for d in devices if d.status == "bound"]

            msg = f"📱 *DAFTAR PERANGKAT AKTIF ({len(online_devs)})*\n━━━━━━━━━━━━━━━━━━\n"
            keyboard = []

            for d in online_devs:
                badge = "🚀" if d.rate_mode == "full" else ("⛔" if d.rate_mode == "blocked" else "⚡")
                msg += f"{badge} *{d.alias_name}* (`{d.ip}`)\n   └ Mode: `{d.current_limit}` | {d.vendor}\n"
                
                # Button for device control
                btn_row = [
                    InlineKeyboardButton(f"🚀 Full", callback_data=f"dev_set:{d.ip}:full"),
                    InlineKeyboardButton(f"⚡ 4M", callback_data=f"dev_set:{d.ip}:standard_4m"),
                    InlineKeyboardButton(f"📱 2M", callback_data=f"dev_set:{d.ip}:sosmed_2m"),
                    InlineKeyboardButton(f"⛔ Blokir", callback_data=f"dev_set:{d.ip}:blocked")
                ]
                keyboard.append(btn_row)

            keyboard.append([InlineKeyboardButton("🔄 Refresh Perangkat", callback_data="btn_refresh_devices")])
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal mengambil daftar perangkat: {e}")

    async def _cmd_full(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_chat.id):
            return
        if not context.args:
            await update.message.reply_text("Format: `/full <IP>` (contoh: `/full 192.168.88.50`)", parse_mode="Markdown")
            return
        ip = context.args[0].strip()
        ok, msg = await engine_instance.set_device_speed(ip, "full", source="telegram")
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

    async def _cmd_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_chat.id):
            return
        if len(context.args) < 2:
            await update.message.reply_text("Format: `/limit <IP> <kecepatan>` (contoh: `/limit 192.168.88.50 2M`)", parse_mode="Markdown")
            return
        ip = context.args[0].strip()
        rate = context.args[1].strip()
        ok, msg = await engine_instance.set_device_speed(ip, "custom", upload_limit=rate, download_limit=rate, source="telegram")
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

    async def _cmd_preset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_chat.id):
            return
        keyboard = [
            [InlineKeyboardButton("🎮 Gaming & Work Priority", callback_data="preset_apply:gaming_work")],
            [InlineKeyboardButton("👨‍👩‍👧‍👦 Family Balanced (4 Mbps)", callback_data="preset_apply:fair_share")],
            [InlineKeyboardButton("⚡ All Full Speed (1 Gbps)", callback_data="preset_apply:all_unrestricted")],
            [InlineKeyboardButton("🌙 Night Saver Mode", callback_data="preset_apply:night_mode")]
        ]
        await update.message.reply_text("🌐 *PILIH PRESET JARINGAN GLOBAL:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "btn_refresh_status":
            stats = await engine_instance.get_system_stats()
            devices = await engine_instance.get_all_devices()
            online_count = sum(1 for d in devices if d.status == "bound")
            msg = (
                f"📊 *STATUS MIKROTIK ROUTEROS*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• *Model*: `{stats.board_name}` (`{stats.version}`)\n"
                f"• *Uptime*: `{stats.uptime}`\n"
                f"• *Beban CPU*: `{stats.cpu_load}%`\n"
                f"• *RAM Bebas*: `{stats.free_memory}` / `{stats.total_memory}`\n"
                f"• *Storage Bebas*: `{stats.free_hdd}` / `{stats.total_hdd}`\n"
                f"• *Jalur Internet*: `{stats.active_wan}`\n\n"
                f"⚡ *Lalu Lintas Saat Ini:*\n"
                f"• ⬇️ Download: `{stats.total_download_str}`\n"
                f"• ⬆️ Upload: `{stats.total_upload_str}`\n"
                f"• 📱 Perangkat Terhubung: `{online_count}` aktif"
            )
            keyboard = [[InlineKeyboardButton("🔄 Refresh Status", callback_data="btn_refresh_status")]]
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "btn_refresh_devices":
            devices = await engine_instance.get_all_devices()
            online_devs = [d for d in devices if d.status == "bound"]
            msg = f"📱 *DAFTAR PERANGKAT AKTIF ({len(online_devs)})*\n━━━━━━━━━━━━━━━━━━\n"
            keyboard = []
            for d in online_devs:
                badge = "🚀" if d.rate_mode == "full" else ("⛔" if d.rate_mode == "blocked" else "⚡")
                msg += f"{badge} *{d.alias_name}* (`{d.ip}`)\n   └ Mode: `{d.current_limit}` | {d.vendor}\n"
                btn_row = [
                    InlineKeyboardButton(f"🚀 Full", callback_data=f"dev_set:{d.ip}:full"),
                    InlineKeyboardButton(f"⚡ 4M", callback_data=f"dev_set:{d.ip}:standard_4m"),
                    InlineKeyboardButton(f"📱 2M", callback_data=f"dev_set:{d.ip}:sosmed_2m"),
                    InlineKeyboardButton(f"⛔ Blokir", callback_data=f"dev_set:{d.ip}:blocked")
                ]
                keyboard.append(btn_row)
            keyboard.append([InlineKeyboardButton("🔄 Refresh Perangkat", callback_data="btn_refresh_devices")])
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("dev_set:"):
            parts = data.split(":")
            ip = parts[1]
            mode = parts[2]
            ok, res_msg = await engine_instance.set_device_speed(ip, mode, source="telegram")
            await query.message.reply_text(f"{'✅' if ok else '❌'} {res_msg}")

        elif data.startswith("preset_apply:"):
            pid = data.replace("preset_apply:", "")
            ok, res_msg = await engine_instance.apply_preset(pid)
            await query.message.reply_text(f"{'✅' if ok else '❌'} {res_msg}")

bot_instance = TelegramBotManager()
