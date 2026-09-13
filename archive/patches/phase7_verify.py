"""Phase 7 final end-to-end verification."""
import json
import os
import subprocess
import sys

from core.historical_storage import get_predictions

CHECKLIST = [
    "predict_match.py",
    "universal_runner.py",
    "team_stats_provider.py",
    "core/historical_storage.py",
    "core/confidence_engine.py",
    "core/schemas.py",
    "core/utils.py",
    "models/soccer_predictor.py",
    "models/basketball_predictor.py",
    "models/baseball_predictor.py",
    "models/tennis_predictor.py",
    "models/tennis_elo.py",
    "models/dispatcher.py",
    "models/soccer_model.py",
    "models/basketball_model.py",
    "models/kbo_model.py",
    "models/soccer_league_config.py",
    "models/soccer_shots_prop_model.py",
    "models/referee_features.py",
    "models/sharp_predict.py",
    "discord_integration.py",
    ".env",
    "prediction_store.py",      # should be MISSING
    "backtest_report.py",       # should be OK (rewritten)
    "tennis_elo.py",            # should be MISSING
    "run_kostyuk_keys_toronto.py",  # should be MISSING
]

EXPECT_MISSING = {"prediction_store.py", "tennis_elo.py", "run_kostyuk_keys_toronto.py"}


def check_files():
    out = []
    for f in CHECKLIST:
        exists = os.path.exists(f)
        expect = "MISSING" if f in EXPECT_MISSING else "OK"
        status = "OK" if exists else "MISSING"
        out.append({"file": f, "status": status, "expected": expect,
                    "match": (expect == status)})
    return out


def run_commands():
    results = {}
    commands = [
        ("soccer", [sys.executable, "universal_runner.py", "--sport", "soccer",
                    "--home", "Ajax", "--away", "PSV", "--league", "Eredivisie",
                    "--market-total", "3.0", "--store-to-db"]),
        ("basketball", [sys.executable, "universal_runner.py", "--sport", "basketball",
                        "--home", "Real Madrid", "--away", "FC Barcelona",
                        "--league", "EuroLeague", "--market-line", "-4.5", "--store-to-db"]),
        ("baseball", [sys.executable, "universal_runner.py", "--sport", "baseball",
                      "--home", "NYY", "--away", "BOS", "--markets", "nrfi", "strikeouts",
                      "--market-total", "8.5",
                      "--home-sp-era", "3.20", "--home-sp-k", "8.5",
                      "--away-sp-era", "4.10", "--away-sp-k", "7.0", "--store-to-db"]),
        ("tennis", [sys.executable, "universal_runner.py", "--sport", "tennis",
                    "--home", "Jannik Sinner", "--away", "Carlos Alcaraz",
                    "--surface", "hard", "--tournament", "US Open",
                    "--round-name", "Final", "--best-of-5", "--store-to-db"]),
    ]
    for name, cmd in commands:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            results[name] = {
                "exit_code": r.returncode,
                "stdout_tail": r.stdout[-500:],
                "stderr_tail": r.stderr[-500:],
            }
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


def count_sports():
    counts = {}
    for sport in ["soccer", "basketball", "baseball", "tennis"]:
        df = get_predictions(sport=sport, db_path="multisport_history.db")
        counts[sport] = int(len(df))
    return counts


def main():
    out = {
        "file_checklist": check_files(),
        "command_results": run_commands(),
        "row_counts_before_after": count_sports(),
    }
    with open("phase7_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("DONE OK")


if __name__ == "__main__":
    main()