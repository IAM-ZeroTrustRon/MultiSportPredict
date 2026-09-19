"""One-off: record the real total price (2.5 Over -125 / Under +100) on the
Toulouse vs Lille prediction so grade_predictions.py settles it at the real
price instead of the -110 default. Safe to delete after grading.
Run locally: venv/Scripts/python.exe patch_toulouse_lille_odds.py
"""
import json
import sqlite3

conn = sqlite3.connect("multisport_history.db")
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT id, model_value, market_value, raw_json FROM predictions "
    "WHERE sport='soccer' AND home_team='Toulouse' AND away_team='Lille' "
    "ORDER BY id DESC LIMIT 1"
).fetchone()

if row is None:
    raise SystemExit("No Toulouse vs Lille row found -- run the prediction first.")

pick = "OVER" if row["model_value"] > row["market_value"] else "UNDER"
price = -125.0 if pick == "OVER" else 100.0

raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
raw.setdefault("market_odds", {})["total_price"] = price

conn.execute("UPDATE predictions SET raw_json=? WHERE id=?", (json.dumps(raw), row["id"]))
conn.commit()
conn.close()

print(f"id={row['id']}  model picked {pick}  ->  recorded price {price:+.0f}")
