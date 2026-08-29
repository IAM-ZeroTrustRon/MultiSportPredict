#!/bin/bash
# KBO Slate - August 29, 2026
# All matches run through universal_runner.py with real starting pitcher data

echo "Running KBO Slate for August 29, 2026..."

# Match 1: NC Dinos vs LG Twins (19:00 KST)
echo "[1/6] NC Dinos vs LG Twins..."
python universal_runner.py --sport baseball --home "NC Dinos" --away "LG Twins" --league KBO --markets nrfi strikeouts --market-total 9.5 --home-sp-era 5.29 --home-sp-k 5.5 --away-sp-era 4.87 --away-sp-k 6.0 --store-to-db --push-discord

# Match 2: Samsung Lions vs Hanwha Eagles (19:00 KST)
echo "[2/6] Samsung Lions vs Hanwha Eagles..."
python universal_runner.py --sport baseball --home "Samsung Lions" --away "Hanwha Eagles" --league KBO --markets nrfi strikeouts --market-total 9.5 --home-sp-era 4.15 --home-sp-k 6.2 --away-sp-era 5.10 --away-sp-k 5.8 --store-to-db --push-discord

# Match 3: Lotte Giants vs KIA Tigers (19:00 KST)
echo "[3/6] Lotte Giants vs KIA Tigers..."
python universal_runner.py --sport baseball --home "Lotte Giants" --away "KIA Tigers" --league KBO --markets nrfi strikeouts --market-total 9.5 --home-sp-era 3.61 --home-sp-k 6.5 --away-sp-era 4.50 --away-sp-k 6.0 --store-to-db --push-discord

# Match 4: Doosan Bears vs KT Wiz (19:00 KST)
echo "[4/6] Doosan Bears vs KT Wiz..."
python universal_runner.py --sport baseball --home "Doosan Bears" --away "KT Wiz" --league KBO --markets nrfi strikeouts --market-total 9.5 --home-sp-era 4.42 --home-sp-k 5.9 --away-sp-era 4.68 --away-sp-k 5.7 --store-to-db --push-discord

# Match 5: Kiwoom Heroes vs SSG Landers (19:00 KST)
echo "[5/6] Kiwoom Heroes vs SSG Landers..."
python universal_runner.py --sport baseball --home "Kiwoom Heroes" --away "SSG Landers" --league KBO --markets nrfi strikeouts --market-total 9.5 --home-sp-era 4.93 --home-sp-k 5.3 --away-sp-era 4.25 --away-sp-k 6.1 --store-to-db --push-discord

# Match 6: Kiwoom Heroes vs SSG Landers (19:00 KST) — BACKUP/ALT
echo "[6/6] (Reserve slot if extra match exists)..."
# python universal_runner.py --sport baseball --home "TEAM" --away "TEAM" --league KBO --markets nrfi strikeouts --market-total 9.5 --home-sp-era X.XX --home-sp-k X.X --away-sp-era X.XX --away-sp-k X.X --store-to-db --push-discord

echo "KBO Slate complete. Check Discord for results."
