"""Run World Cup soccer match prediction: South Africa vs Canada.

This script uses the repo's existing soccer prediction engine:
- models/soccer_predict_game.py (run_soccer_game)

It writes outputs to:
- output/soccer/South_Africa_vs_Canada.json
- output/worldcup_results.json (append-safe)
- output/multisport_results.csv (append a compatible row)

Discord push:
- Optional; only if DISCORD_WEBHOOK_URL is set and signature matches.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _safe_append_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(json.dumps([payload], indent=2, ensure_ascii=False), encoding="utf-8")
        return

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, list):
            existing.append(payload)
        else:
            existing = [existing, payload]
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except json.JSONDecodeError:
        path.write_text(json.dumps([payload], indent=2, ensure_ascii=False), encoding="utf-8")


def _append_multisport_csv(row: Dict[str, Any], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "timestamp",
        "record_type",
        "game_id",
        "date",
        "league",
        "home_team",
        "away_team",
        "entity_name",
        "stat_name",
        "stat_value",
        "secondary_value",
        "market_line",
        "current_line",
        "open_line",
        "notes",
        "model_score",
        "model_prob",
        "lean",
        "details",
    ]

    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    if write_header:
        csv_path.write_text(",".join(header) + "\n", encoding="utf-8")

    def _csv_escape(v: Any) -> str:
        s = "" if v is None else str(v)
        if any(ch in s for ch in [",", '"', "\n"]):
            s = s.replace('"', '""')
            return f'"{s}"'
        return s

    line = ",".join(_csv_escape(row.get(col, "")) for col in header)
    with csv_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(push_discord: bool = False) -> Dict[str, Any]:
    home_team = "South Africa"
    away_team = "Canada"
    league = "World Cup"
    game_date = "2026-06-16"

    # Market defaults (not provided by user). Use repo defaults.
    # If you later have real lines, pass them by editing these values.
    market_total = 2.5
    market_corners = 9.5
    market_line = 0.25

    from soccer.soccer_predict_game import run_soccer_game


    result = run_soccer_game(
        home_team=home_team,
        away_team=away_team,
        market_line=market_line,
        market_total=market_total,
        market_corners=market_corners,
        store_to_db=True,
    )

    # Record files
    match_file = Path("output/soccer") / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}.json"

    # Append to worldcup results
    worldcup_path = Path("output/worldcup_results.json")
    _safe_append_json(
        worldcup_path,
        {
            "ts": datetime.utcnow().isoformat() + "Z",
            "league": league,
            "date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "predictions": {
                "total_goals": result.get("game", {}).get("projected_total_goals"),
                "over_25_prob": result.get("goals_analysis", {}).get("over_25_prob"),
                "btts_probability": result.get("btts_probability"),
            },
            "files": {
                "match_json": str(match_file),
            },
            "source": "run_worldcup_sa_vs_can_2026_06_16.py",
        },
    )

    # Append a compatible row to multisport_results.csv
    csv_path = Path("output/multisport_results.csv")
    btts_prob = float(result.get("btts_probability", 0.0))

    # Build lean from BTTS recommendation
    btts_rec = result.get("predictions", {}).get("btts", {}).get("recommendation", "Pass")

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "record_type": "soccer_btts",
        "game_id": f"WC-{game_date}-{home_team}-{away_team}".replace(" ", "_"),
        "date": game_date,
        "league": league,
        "home_team": home_team,
        "away_team": away_team,
        "entity_name": "btts",
        "stat_name": "btts_probability",
        "stat_value": round(btts_prob * 100.0, 3),
        "secondary_value": "",
        "market_line": "0.5",
        "current_line": "",
        "open_line": "",
        "notes": "World Cup BTTS record (model-driven)",
        "model_score": result.get("predictions", {}).get("btts", {}).get("confidence"),
        "model_prob": round(btts_prob, 4),
        "lean": btts_rec,
        "details": f"BTTS recommendation={btts_rec}; projected_total={result.get('game', {}).get('projected_total_goals')}",
    }

    _append_multisport_csv(row, csv_path)

    # Optional Discord push (only if configured and compatible signature)
    if push_discord and os.getenv("DISCORD_WEBHOOK_URL"):
        try:
            from universal_runner import push_to_discord

            # universal_runner.push_to_discord expects different args than discord_integration.push_to_discord
            # Use minimal known arguments for soccer push helper.
            push_to_discord(
                sport="soccer",
                home=home_team,
                away=away_team,
                market_total=market_total,
                projected_total=result.get("game", {}).get("projected_total_goals"),
                edge=str(result.get("predictions", {}).get("total", {}).get("edge", 0.0)),
                recommendation=f"BTTS: {btts_rec}",
                confidence=float(result.get("predictions", {}).get("btts", {}).get("confidence", 50.0)),
                webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
                extra_metrics=f"Over 2.5: {result.get('goals_analysis', {}).get('over_25_prob')} ; BTTS: {btts_prob}",
            )
        except Exception:
            # Keep task focused on recording; ignore push errors.
            pass

    return result


if __name__ == "__main__":
    run(push_discord=True)

