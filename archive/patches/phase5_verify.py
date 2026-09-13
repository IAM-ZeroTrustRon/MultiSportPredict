"""Phase 5 verification: confirm a row landed in core.historical_storage."""
import json

from core.historical_storage import get_predictions

def main():
    db_path = "multisport_history.db"
    rows = get_predictions(sport="soccer", db_path=db_path)

    out = {
        "soccer_row_count": int(len(rows)),
        "latest_rows": [],
    }
    if not rows.empty:
        tail = rows.head(3)
        for _, row in tail.iterrows():
            out["latest_rows"].append({
                "sport": row.get("sport"),
                "home_team": row.get("home_team"),
                "away_team": row.get("away_team"),
                "market_type": row.get("market_type"),
                "model_value": row.get("model_value"),
                "market_value": row.get("market_value"),
                "edge": row.get("edge"),
                "confidence": row.get("confidence"),
                "recommendation": row.get("recommendation"),
                "timestamp": row.get("timestamp"),
            })

    with open("phase5_verify_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("DONE OK")

if __name__ == "__main__":
    main()