# 🛡️ Kebijakan Keamanan (Security Policy)

## Pelaporan Kerentanan Keamanan

Keamanan data jaringan dan kredensial router adalah prioritas tertinggi dalam pengembangan **MikroTik Bandwidth Manager**.

Jika Anda menemukan potensi kerentanan keamanan (*vulnerability*), mohon **JANGAN** membuat issue publik. Ikuti langkah pelaporan yang bertanggung jawab berikut:

1. Buat **Private Security Advisory** langsung melalui tab [Security Advisories](https://github.com/febriazkad-hub/mikrotik-bandwidth-manager/security/advisories) di repositori ini.
2. Jelaskan model ancaman, langkah reproduksi (PoC), dan dampak potensial.
3. Tim pemelihara akan merespons dalam waktu 48 jam dan menyediakan perbaikan (*patch*) sebelum pengungkapan publik.

## Pedoman Kredensial & Penggunaan

- Aplikasi ini berkomunikasi dengan router via SSH CLI atau REST API. Selalu gunakan user dengan izin yang sesuai.
- Jangan pernah membagikan file `.env` atau `config.json` yang memuat password router.
- Seluruh antrean dibuat secara aman dan tidak merusak konfigurasi firewall bawaan selain aturan FastTrack yang dapat diaktifkan kembali sewaktu-waktu.
