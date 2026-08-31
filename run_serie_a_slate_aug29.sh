#!/bin/bash
echo "Running Serie A Slate - August 29, 2026..."

python run_match_safe.py --sport soccer --home "AC Milan" --away "Inter Milan" --league "Serie A" --market-total 2.75 --store-to-db --push-discord --allow-placeholder
python run_match_safe.py --sport soccer --home "Juventus" --away "Roma" --league "Serie A" --market-total 2.75 --store-to-db --push-discord --allow-placeholder
python run_match_safe.py --sport soccer --home "Napoli" --away "Lazio" --league "Serie A" --market-total 2.75 --store-to-db --push-discord --allow-placeholder
python run_match_safe.py --sport soccer --home "Atalanta" --away "Fiorentina" --league "Serie A" --market-total 2.75 --store-to-db --push-discord --allow-placeholder

echo "Serie A slate complete."
