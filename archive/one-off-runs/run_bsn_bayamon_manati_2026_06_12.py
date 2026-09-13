"""Run BSN matchup: Baamon cattle Herder vs Manati (Osos de Manatí)

- Uses the provided historical baseline (June 12, 2026: Manatí 98-93 Bayamón)
- Uses provided market probabilities:
    Moneyline: Bayamón 46.5% (away), Manatí 53.5% (home)
    Total O/U 182.5: Over 61.2%
    Projected total: 187.4 points
- Pushes results to Discord (if DISCORD_WEBHOOK_URL is configured)
- Records all results to disk:
    - output/basketball/<match>.json
    - output/bsn_results.json (append-safe)
    - output/multisport_results.csv (append row compatible with existing columns)

The goal of this script is to provide deterministic output and a durable record.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Discord push is optional; imported lazily to avoid hard dependency on requests.



def _safe_append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    """Append a single JSON object to a JSON array file safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(json.dumps([payload], indent=2), encoding="utf-8")
        return

    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, list):
            existing.append(payload)
        else:
            existing = [existing, payload]
        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except json.JSONDecodeError:
        # If file is corrupted/not JSON, fall back to wrap as list with current payload
        path.write_text(json.dumps([payload], indent=2), encoding="utf-8")


def run_bsn_bayamon_manati(push_discord_flag: bool = True) -> Dict[str, Any]:
    home_team = "Osos de Manatí"
    away_team = "Vaqueros de Bayamón"

    league = "Baloncesto Superior Nacional"
    game_date = "2026-06-12"

    # Provided baseline / market inputs
    baseline_game = {
        "date": "2026-06-12",
        "final_score": "Osos de Manatí 98-93 Vaqueros de Bayamón",
        "field_goal_efficiency": {"Manatí": 0.53, "Bayamón": 0.51},
        "three_point": {"Manatí": "50% (12/24)", "Bayamón": "37% (10/27)"},
        "rebounding": {"total_rebounds": 29, "off_def_split_each": {"off": 7, "def": 22}},
        "free_throws": {"Bayamón_ft_pct": 0.864, "Manatí_ft_attempts": 31, "Manatí_ft_made": 22, "Bayamón_ft_attempts": 22},
        "discipline": {"Bayamón_turnovers": 15, "Manatí_turnovers": 11},
    }

    moneyline_probs = {
        "Bayamón_ml_implied_prob": 0.465,
        "Manatí_ml_implied_prob": 0.535,
    }

    total_market = {
        "ou_line": 182.5,
        "over_prob": 0.612,
        "under_prob": 0.388,
        "projected_total": 187.4,
    }

    projected = {
        # We don't have the exact model's split; we keep total deterministic.
        # A simple split: allocate 52% of total to home based on provided ML.
        "projected_total": total_market["projected_total"],
        "home_share_of_total": moneyline_probs["Manatí_ml_implied_prob"],
    }
    projected_home = round(projected["projected_total"] * projected["home_share_of_total"], 1)
    projected_away = round(projected["projected_total"] - projected_home, 1)

    result: Dict[str, Any] = {
        "sport": "basketball",
        "league": league,
        "game": {
            "date": game_date,
            "home_team": home_team,
            "away_team": away_team,
        },
        "inputs": {
            "historical_baseline": baseline_game,
            "market_probabilities": {
                "moneyline_implied_prob": {
                    "away": moneyline_probs["Bayamón_ml_implied_prob"],
                    "home": moneyline_probs["Manatí_ml_implied_prob"],
                },
                "totals": total_market,
            },
        },
        "projections": {
            "projected_home_score": projected_home,
            "projected_away_score": projected_away,
            "projected_total": total_market["projected_total"],
            "moneyline": {
                "home_win_probability": moneyline_probs["Manatí_ml_implied_prob"],
                "away_win_probability": moneyline_probs["Bayamón_ml_implied_prob"],
            },
            "total_market": {
                "over_prob": total_market["over_prob"],
                "under_prob": total_market["under_prob"],
                "over_label": f"Over {total_market['ou_line']}",
                "under_label": f"Under {total_market['ou_line']}",
            },
        },
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "record_id": f"{league}-{home_team}-{away_team}-{game_date}".replace(" ", "_"),
        },
    }

    # 1) Write match JSON
    out_dir = Path("output/basketball")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}_{game_date}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2) Append to durable BSN record file
    bsn_record_path = Path("output/bsn_results.json")
    _safe_append_jsonl(
        bsn_record_path,
        {
            "ts": datetime.utcnow().isoformat() + "Z",
            "league": league,
            "date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "moneyline_home_prob": moneyline_probs["Manatí_ml_implied_prob"],
            "total_over_prob": total_market["over_prob"],
            "projected_total": total_market["projected_total"],
            "projected_home": projected_home,
            "projected_away": projected_away,
            "details": {
                "baseline": baseline_game.get("final_score"),
                "three_point": baseline_game.get("three_point"),
                "rebounds": baseline_game.get("rebounding"),
                "turnovers": baseline_game.get("discipline"),
            },
            "source": "provided_market_inputs",
            "files_written": [str(out_path)],
        },
    )

    # 3) Append row to output/multisport_results.csv with existing columns.
    #    We'll add a small subset of fields; missing columns will be empty.
    csv_path = Path("output/multisport_results.csv")
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

    game_id = f"BSN-{game_date}-{home_team}-{away_team}".replace(" ", "_")
    ts = datetime.utcnow().isoformat()

    # Deterministic lean labels
    moneyline_home_prob_pct = round(moneyline_probs["Manatí_ml_implied_prob"] * 100.0, 1)
    over_prob_pct = round(total_market["over_prob"] * 100.0, 1)

    row: Dict[str, Any] = {
        "timestamp": ts,
        "record_type": "game",
        "game_id": game_id,
        "date": game_date,
        "league": league,
        "home_team": home_team,
        "away_team": away_team,
        "entity_name": "market",
        "stat_name": "moneyline_home_win_and_total_over",
        "stat_value": moneyline_home_prob_pct,
        "secondary_value": over_prob_pct,
        "market_line": total_market["ou_line"],
        "current_line": "",
        "open_line": "",
        "notes": "Provided inputs baseline; deterministic record write.",
        "model_score": "",
        "model_prob": over_prob_pct,
        "lean": "Over & Manatí (implied)" if over_prob_pct >= 60 and moneyline_home_prob_pct >= 53 else "Neutral",
        "details": f"baseline={baseline_game.get('final_score')}; projected_total={total_market['projected_total']} ; projected_score={projected_home}-{projected_away}",
    }

    # Ensure header exists (file may already exist with header)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    if write_header:
        csv_path.write_text(",".join(header) + "\n", encoding="utf-8")

    def _csv_escape(v: Any) -> str:
        s = "" if v is None else str(v)
        if any(ch in s for ch in [',', '"', '\n']):
            s = s.replace('"', '""')
            return f'"{s}"'
        return s

    line = ",".join(_csv_escape(row.get(col, "")) for col in header)
    with csv_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    # 4) Push to Discord (optional; imported lazily to avoid hard dependency on requests)
    if push_discord_flag:
        from discord_integration import push_to_discord

        recommendation = (
            f"ML: {home_team} {moneyline_home_prob_pct:.1f}% | "
            f"Total: Over {total_market['ou_line']} {over_prob_pct:.1f}%"
        )
        confidence = float(round(max(moneyline_home_prob_pct, over_prob_pct), 1))
        edge = f"ML {moneyline_home_prob_pct - 50.0:+.1f}% (vs 50/50)"  # informational
        push_to_discord(
            sport="basketball",
            home=home_team,
            away=away_team,
            recommendation=recommendation,
            confidence=confidence,
            edge=edge,
            market_total=total_market["ou_line"],
            webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        )



    # Return for programmatic use
    result["files_written"] = {
        "match_json": str(out_path),
        "bsn_record_json": str(bsn_record_path),
        "csv": str(csv_path),
    }
    return result


if __name__ == "__main__":
    run_bsn_bayamon_manati(push_discord_flag=True)

