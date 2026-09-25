# 📶 MikroTik Smart Bandwidth Manager v2

Aplikasi manajemen jaringan dan bandwidth cerdas untuk **MikroTik RouterOS** (mendukung RouterOS v6 dan v7). Dilengkapi dengan antarmuka **Web Dashboard responsif modern (Dark Mode)**, **In-Browser SSH Web Terminal (xterm.js)**, **Wake-on-LAN (WOL)**, **Tools Diagnostik (Ping, Traceroute, DNS, ARP)**, **Firewall Viewer**, **Security Hardening Audit**, **Backup & Export**, serta **Interactive Telegram Bot Controller**. Siap dijalankan menggunakan **Docker (Docker Compose / CasaOS)** maupun langsung di Windows / Linux.

---

## 🌟 Fitur Unggulan v2

### 1. ⚡ Wake-on-LAN (WOL) 1-Klik
- Tombol **Wake (WOL)** di kartu perangkat PC Workstation (`40:16:7E:23:A0:8A`) dan Server Debian 13 (`00:E0:4C:A6:32:5C`).
- Mengirim Magic Packet langsung dari antarmuka router (`/tool wol mac=... interface=bridgeLAN`) untuk menyalakan PC yang sedang mati.

### 2. 🖥️ In-Browser SSH Terminal (xterm.js)
- Terminal interaktif MikroTik langsung dari browser via WebSocket bridge ke Paramiko SSH PTY channel.
- Akses penuh CLI RouterOS tanpa perlu membuka Winbox atau PuTTY.

### 3. 🔧 Alat Diagnostik Jaringan Bawaan
- **Ping Test**: Uji latensi dan packet loss langsung dari router ke IP/domain eksternal.
- **Traceroute**: Pelacakan rute hop-by-hop jaringan.
- **DNS Resolve**: Uji resolusi nama domain via cache MikroTik.
- **Live ARP Table**: Tampilan real-time tabel ARP (`/ip arp`) pemetaan IP ke MAC.

### 4. 🛡️ Firewall Rules Viewer
- Tampilan aturan firewall terorganisir per sub-tab: **Filter Rules**, **NAT Rules**, **Mangle**, dan **Address Lists**.
- Label aksi berwarna (`ACCEPT`, `DROP`, `MASQUERADE`, `DST-NAT`).

### 5. 🔒 Security Hardening Audit & Scorecard
- Audit keamanan router otomatis dengan skor 0–100% (Green/Yellow/Red indicator).
- Pemeriksaan layanan berbahaya (Telnet, FTP, WWW), port SSH kustom, proteksi input chain, DNS open resolver cache, dan bandwidth test server.

### 6. 💾 Backup & Export Konfigurasi Router
- Ekspor konfigurasi penuh script `.rsc` (`/export compact hide-sensitive`) dengan caching cerdas.
- 1-Klik tombol **Download .rsc** untuk backup offline cepat.
- Informasi hardware RouterBOARD (Model, Serial, Firmware).

### 7. 🔄 Tindakan Daya Router (Reboot)
- Tombol reboot router jarak jauh dengan dialog konfirmasi ganda di modal Settings.

### 8. 📊 Real-Time Throughput & Bandwidth QoS
- Telemetri live hardware rate (`/interface monitor-traffic`) streaming via WebSocket setiap 1 detik.
- Tombol kecepatan 1-klik (`Full 1G`, `10M`, `4M`, `2M`, `1M`, `Blokir`) dan Slider Kustom dengan chip angka cepat.
- Preset Global: `Gaming & Work`, `Family (4M PCQ)`, `All Full Speed`, `Night Saver`.
- Otomasi jadwal pembatasan waktu (Parental Control).
- Telegram Bot interaktif dua arah.

### 9. 📜 RouterOS Live System Logs & SQLite Archiver (Debian 13)
- Ekstraksi log sistem MikroTik secara langsung via SSH (`/log print detail`) tanpa membebani flash disk atau RAM router.
- **Penyimpanan Abadi di SQLite**: Log MikroTik diarsipkan ke database SQLite Debian 13 (`data/mikrotik_manager.db`) dengan batas 5.000 log riwayat terindeks.
- **Visual Severity Badging**: Penanda visual kategori warna untuk `ERROR`/`CRITICAL` (merah), `WARN` (kuning), `AUTH/LOGIN` (hijau), dan `INFO` (cyan).
- **Filter Cepat & Live Search**: Filter instan berdasarkan level keparahan (Error, Warning, Login), topik (DHCP, SSTP, System, Wireless, Firewall), serta pencarian kata kunci.
- **Sinkronisasi Otomatis**: Background scheduler mensinkronkan log terbaru setiap 60 detik serta tombol sinkronisasi manual instan di web UI.

---

## 🚀 Cara Menjalankan

### Opsi 1: Menjalankan via Docker Compose (Rekomendasi untuk Debian / CasaOS)

```bash
docker-compose up -d --build
```
Buka browser di `http://<IP-SERVER>:5678` (misal: `http://192.168.77.16:5678` atau `http://100.87.210.60:5678` via Tailscale).

#### Deploy di CasaOS:
- Buka CasaOS ➔ Klik **+ (Install a customized app)** ➔ Klik **Import** ➔ Pilih `docker-compose.yml` ➔ **Submit**.

---

### Opsi 2: Menjalankan di Windows Lokal

1. Buka folder `C:\Users\Administrator\MikroTik_Bandwidth_Manager\scripts`.
2. Klik ganda `run_local.bat` (atau gunakan shortcut Desktop `MikroTik Bandwidth Manager.lnk`).
3. Buka browser di `http://localhost:5678` atau `http://192.168.77.29:5678`.

---

## 🌐 Cara Mengakses Dari Mana Saja

1. **Jaringan Rumah (LAN / Wi-Fi)**: `http://192.168.77.29:5678` atau `http://192.168.77.16:5678`
2. **Jarak Jauh via Tailscale**: `http://100.91.219.53:5678` (PC m1) atau `http://100.87.210.60:5678` (Debian Server)
3. **Jarak Jauh via Telegram Bot**: Chat bot langsung tanpa perlu VPN.

---

## ⚙️ Konfigurasi Environment (`.env` / `config.json`)

| Variabel | Default | Keterangan |
| :--- | :--- | :--- |
| `MIKROTIK_HOST` | `192.168.77.1` | Alamat IP Router MikroTik |
| `MIKROTIK_PORT` | `221` | Port SSH MikroTik |
| `MIKROTIK_USER` | `admin` | Username RouterOS |
| `MIKROTIK_PASS` | `rty` | Password RouterOS |
| `WEB_PORT` | `5678` | Port Web GUI Dashboard |
| `TELEGRAM_BOT_TOKEN` | *opsional* | Token Bot Telegram dari @BotFather |
| `TELEGRAM_ALLOWED_CHAT_ID` | *opsional* | Chat ID Telegram pemilik |
