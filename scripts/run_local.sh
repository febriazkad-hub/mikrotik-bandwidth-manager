#!/usr/bin/env bash
cd "$(dirname "$0")/.."
echo "===================================================="
echo "  MikroTik Smart Bandwidth Manager (FastAPI + Web)"
echo "===================================================="
echo "Menjalankan Web Dashboard di http://0.0.0.0:5678 ..."
python3 -m app.main
