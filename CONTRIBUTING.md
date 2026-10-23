# 🤝 Panduan Kontribusi (Contributing Guide)

Terima kasih atas ketertarikan Anda untuk berkontribusi pada **MikroTik Bandwidth Manager**! Proyek ini terbuka bagi seluruh komunitas pegiat jaringan dan open-source.

## Cara Berkontribusi

1. **Fork Repositori** ke akun GitHub Anda.
2. **Clone ke Lokal**:
   ```bash
   git clone https://github.com/<username>/mikrotik-bandwidth-manager.git
   cd mikrotik-bandwidth-manager
   ```
3. **Buat Branch Fitur**:
   ```bash
   git checkout -b feature/nama-fitur-baru
   ```
4. **Siapkan Environment & Dependensi**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # atau venv\Scripts\activate di Windows
   pip install -r requirements.txt
   pip install pytest pytest-asyncio
   ```
5. **Jalankan Unit Test**:
   ```bash
   pytest tests/ -v
   ```
6. **Commit & Push**:
   Pastikan commit message jelas dan tidak memuat kredensial atau IP pribadi:
   ```bash
   git commit -m "feat: tambahkan fitur auto-reconnect SSH"
   git push origin feature/nama-fitur-baru
   ```
7. **Buka Pull Request (PR)** melalui antarmuka GitHub.
