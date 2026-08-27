"""
run_match_safe.py - refuses to run a soccer/basketball match unless real
team data is on file, instead of letting it silently fall through to
placeholders. This is a HARD gate, not a warning - it exits before the
match ever runs if data is missing, unless you explicitly override it.

Usage (same args as universal_runner.py, plus this wrapper's own logic):
    python run_match_safe.py --sport soccer --home "Real Madrid" --away "Real Sociedad" --league "La Liga" --market-total 3.5 --store-to-db --push-discord
    python run_match_safe.py --sport soccer --home "Some Unseeded FC" --away "Other FC" --league "X" --allow-placeholder
"""
import argparse
import subprocess
import sys

from team_stats_provider import get_soccer_team_stats, get_basketball_team_stats


def check_soccer_or_basketball(sport, home, away):
    getter = get_soccer_team_stats if sport in ("soccer", "football") else get_basketball_team_stats
    home_stats = getter(home)
    away_stats = getter(away)
    missing = []
    if home_stats is None:
        missing.append(home)
    if away_stats is None:
        missing.append(away)
    return missing


def check_baseball(args):
    missing = []
    if args.home_sp_era is None or args.home_sp_k is None:
        missing.append("home starting pitcher ERA/K")
    if args.away_sp_era is None or args.away_sp_k is None:
        missing.append("away starting pitcher ERA/K")
    return missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--allow-placeholder", action="store_true",
                         help="Explicitly allow running with missing real data. "
                              "Use only for genuine no-data-exists leagues (e.g. Norway 1. Division).")
    parser.add_argument("--home-sp-era", type=float, default=None)
    parser.add_argument("--home-sp-k", type=float, default=None)
    parser.add_argument("--away-sp-era", type=float, default=None)
    parser.add_argument("--away-sp-k", type=float, default=None)
    args, passthrough_args = parser.parse_known_args()

    sport = args.sport.strip().lower()

    if sport in ("soccer", "football", "basketball", "kbl", "euroleague"):
        missing = check_soccer_or_basketball(sport, args.home, args.away)
    elif sport in ("baseball", "mlb", "kbo"):
        missing = check_baseball(args)
    else:
        missing = []
        print(f"[NOTE] No data-quality gate defined yet for sport '{sport}' - proceeding without a check.")

    if missing and not args.allow_placeholder:
        print("=" * 60)
        print("BLOCKED: real data missing, prediction NOT run.")
        print("=" * 60)
        print(f"Missing real data for: {missing}")
        print("")
        print("This match would otherwise silently use placeholder values,")
        print("which produces a confident-looking but untrustworthy prediction.")
        print("")
        print("To fix: seed real data first (see seed_todays_matches.py pattern),")
        print("then re-run this exact command.")
        print("")
        print("If this is a genuine no-real-data-exists league (e.g. lower-tier")
        print("leagues with no FBref coverage), re-run with --allow-placeholder")
        print("to proceed anyway, on purpose, with full awareness.")
        sys.exit(1)

    if missing and args.allow_placeholder:
        print(f"[OVERRIDE] Proceeding with placeholder data for: {missing} (--allow-placeholder set)")

    cmd = [sys.executable, "universal_runner.py", "--sport", args.sport,
           "--home", args.home, "--away", args.away]
    if args.home_sp_era is not None:
        cmd += ["--home-sp-era", str(args.home_sp_era)]
    if args.home_sp_k is not None:
        cmd += ["--home-sp-k", str(args.home_sp_k)]
    if args.away_sp_era is not None:
        cmd += ["--away-sp-era", str(args.away_sp_era)]
    if args.away_sp_k is not None:
        cmd += ["--away-sp-k", str(args.away_sp_k)]
    cmd += passthrough_args

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
