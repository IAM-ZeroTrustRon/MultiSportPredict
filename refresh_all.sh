#!/usr/bin/env bash
set -euo pipefail

echo "=== STARTING DAILY REAL-DATA INGESTION ==="
python ingest_mlb.py
python ingest_soccer.py
python ingest_hoops.py
echo "=== ALL DATA FRESHLY SEEDED. READY FOR PREDICTIONS. ==="