# 🚀 MikroTik Bandwidth Manager

<p align="center">
  <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/mikrotik-light.svg" width="96" height="96" alt="MikroTik Bandwidth Manager Logo" />
</p>

<p align="center">
  <strong>Platform Web Kontrol Bandwidth, Telemetri Real-Time & Manajemen Perangkat Otomatis untuk MikroTik RouterOS (v6 & v7)</strong>
</p>

<p align="center">
  <a href="https://github.com/febriazkad-hub/mikrotik-bandwidth-manager/actions/workflows/ci.yml"><img src="https://github.com/febriazkad-hub/mikrotik-bandwidth-manager/actions/workflows/ci.yml/badge.svg" alt="CI Tests" /></a>
  <a href="https://github.com/febriazkad-hub/mikrotik-bandwidth-manager/actions/workflows/codeql.yml"><img src="https://github.com/febriazkad-hub/mikrotik-bandwidth-manager/actions/workflows/codeql.yml/badge.svg" alt="CodeQL" /></a>
  <img src="https://img.shields.io/badge/RouterOS-v6%20%7C%20v7-blue.svg?logo=mikrotik" alt="RouterOS" />
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platforms-amd64%20%7C%20arm64%20%7C%20armv7-orange.svg?logo=docker" alt="Multi-Arch" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" /></a>
</p>

---

## 🌟 Mengapa MikroTik Bandwidth Manager?

Mengelola pembagian bandwidth dan antrean pada router MikroTik seringkali membutuhkan keahlian teknis Winbox atau terminal CLI yang rumit. **MikroTik Bandwidth Manager (BWM)** hadir sebagai solusi *Zero-Config* modern: cukup colokkan router kondisi default bawaan pabrik (`192.168.88.1`), dan dashboard web yang intuitif siap mengatur seluruh lalu lintas internet rumah atau kantor Anda dalam hitungan detik.

Ringan, responsif, dan hemat daya—berjalan sempurna bahkan pada router kelas *entry* seperti **hAP lite (RB941-2nD)** hingga router berkecepatan tinggi seperti **hEX (RB750Gr3)** dan **hAP ax² / CCR series**.

---

## ✨ Fitur Utama

- ⚡ **Zero-Config Setup Wizard**: Deteksi hardware otomatis, auto-discovery jalur internet (WAN) dan antarmuka lokal (LAN Bridge), serta verifikasi RouterOS v6/v7 tanpa konfigurasi manual yang membingungkan.
- 🎛️ **Kontrol Kecepatan 1-Klik**: Atur profil limit perangkat (*Full Speed*, *Standard 4M*, *Sosmed 2M*, *Hemat 1M*, atau *Blokir Internet*) seketika.
- 📊 **Telemetri Live WebSocket**: Grafik lalu lintas unggah (*upload*) dan unduh (*download*) real-time berkecepatan 1 detik dengan pemantauan beban CPU router.
- 🛡️ **FastTrack QoS Resolver**: Resolusi dilema FastTrack RouterOS secara non-destruktif. Mengizinkan *Simple Queue* membatasi kecepatan secara akurat tanpa merusak konfigurasi firewall asli.
- 📱 **Pencarian Vendor Hardware Offline**: Identifikasi otomatis merek perangkat (Apple, Samsung, Xiaomi, Intel, Espressif, Raspberry Pi, dll.) berdasarkan database IEEE OUI lokal tanpa membebani koneksi luar.
- ⚡ **Universal Wake-on-LAN (WOL)**: Hidupkan PC, workstation, atau server rumah Anda dari jarak jauh langsung melalui perintah router.
- 💻 **In-Browser Terminal (xterm.js)**: Terminal shell RouterOS interaktif langsung di dalam browser tanpa perlu membuka aplikasi PuTTY atau SSH client terpisah.
- 🤖 **Telegram Bot Assistant**: Pantau jaringan, cek perangkat aktif, dan ubah kecepatan internet dari mana saja melalui aplikasi Telegram di ponsel pintar Anda.
- 🧹 **Clean Detach (Safe Uninstall)**: Kembalikan kondisi router 100% bersih ke setelan pabrik hanya dengan satu klik tombol bila aplikasi tidak lagi digunakan.

---

## 🚀 Panduan Memulai Cepat (Quickstart)

### Opsi 1: Docker CLI (Rekomendasi)

Jalankan container dalam 1 baris perintah:

```bash
docker run -d \
  --name mikrotik-bandwidth-manager \
  --restart unless-stopped \
  -p 5678:5678 \
  -v $(pwd)/data:/app/data \
  ghcr.io/febriazkad-hub/mikrotik-bandwidth-manager:latest
```

Buka browser Anda di `http://<ip-server>:5678` dan ikuti **Setup Wizard** 3-langkah untuk menghubungkan ke router MikroTik Anda!

---

### Opsi 2: Docker Compose

Salin file `docker-compose.yml`:

```yaml
services:
  mikrotik-bandwidth-manager:
    image: ghcr.io/febriazkad-hub/mikrotik-bandwidth-manager:latest
    container_name: mikrotik-bandwidth-manager
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - MIKROTIK_HOST=192.168.88.1
      - MIKROTIK_PORT=22
      - MIKROTIK_USER=admin
      - MIKROTIK_PASS=
      - WEB_PORT=5678
    volumes:
      - ./data:/app/data
```

Jalankan:
```bash
docker compose up -d
```

---

### Opsi 3: Instalasi di CasaOS / ZimaOS

1. Buka dashboard CasaOS Anda.
2. Klik **App Store** -> **Custom Install**.
3. Masukkan `ghcr.io/febriazkad-hub/mikrotik-bandwidth-manager:latest` pada kolom image.
4. Petakan port Web ke `5678` dan volume `/DATA/AppData/mikrotik-bandwidth-manager:/app/data`.
5. Klik **Submit**.

---

## 🛠️ Matriks Kompatibilitas Hardware

| Model MikroTik | Arsitektur | RouterOS | Status Uji Coba |
|---|---|---|---|
| **hAP lite (RB941-2nD)** | smips (650MHz) | v6.49.x / v7.x | 🟢 100% Stabil (<15% CPU) |
| **hEX (RB750Gr3)** | mmips | v6.49.x / v7.x | 🟢 100% Kompatibel |
| **hAP ac² / ac³** | arm | v6.49.x / v7.x | 🟢 100% Kompatibel |
| **hAP ax² / ax³** | arm64 | v7.x | 🟢 100% Kompatibel (REST + SSH) |
| **CHR (Cloud Hosted Router)** | x86_64 | v6 / v7 | 🟢 100% Kompatibel |

---

## 🔒 Keamanan & Privasi

- **Zero Secrets**: Aplikasi tidak pernah menyimpan sandi Anda di cloud publik. Seluruh data konfigurasi disimpan dalam database SQLite lokal di dalam container (`/app/data/mikrotik_manager.db`).
- **Non-Destructive Rules**: Penyesuaian aturan FastTrack firewall dilakukan secara aman (`disabled=yes` dengan label audit) dan dapat dipulihkan sewaktu-waktu tanpa menghapus konfigurasi pabrik MikroTik.
- **Unprivileged Container**: Citra Docker resmi berjalan dengan user non-root (`appuser`, UID 10001) untuk memitigasi risiko keamanan container escape.

---

## 🤝 Kontribusi

Kontribusi dari komunitas sangat disambut hangat! Silakan baca [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan pembuatan pull request, pengujian unit test mock, dan pelaporan isu kompatibilitas model router baru.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah naungan **[MIT License](LICENSE)**. Bebas digunakan, dimodifikasi, dan didistribusikan untuk keperluan pribadi maupun komersial.
