"""
prep_match_data.py - tells you exactly what to look up and gives you a
ready-to-fill template, instead of discovering missing data after the
fact via the placeholder warning.

Usage:
    python prep_match_data.py --sport soccer --home "Real Madrid" --away "Real Sociedad"
"""
import argparse
from team_stats_provider import get_soccer_team_stats, get_basketball_team_stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sport", required=True)
    p.add_argument("--home", required=True)
    p.add_argument("--away", required=True)
    args = p.parse_args()

    sport = args.sport.strip().lower()
    if sport in ("soccer", "football"):
        getter = get_soccer_team_stats
    elif sport in ("baseball", "mlb", "kbo"):
        print(f"[NOTE] {sport.upper()} uses starting pitcher stats (--home-sp-era, --home-sp-k), not team seeding.")
        print("No data check needed. Run directly via universal_runner.py with SP overrides.")
        sys.exit(0)
    else:
        getter = get_basketball_team_stats

    for team in (args.home, args.away):
        existing = getter(team)
        print("=" * 60)
        print(team)
        print("=" * 60)
        if existing:
            print("[ALREADY SEEDED]")
            for k, v in existing.items():
                print(f"  {k}: {v}")
            print("(Re-run upsert to update if this is stale.)")
            continue

        print("[NOT SEEDED - look these up before running this match]")
        print("")
        if sport in ("soccer", "football"):
            print(f"  Search: https://fbref.com/en/search/search.fcgi?search={team.replace(' ', '+')}")
            print(f"  Search: https://footystats.org/search?query={team.replace(' ', '+')}")
            print("  Minimum needed (stops placeholder mode): goals_for, goals_against (last 5-10 matches)")
            print("  Better (if available): xg_for, xg_against, shots, sot, clean_sheets")
            print("  Also check: confirmed injuries (missing_attacker/creator/cb/gk)")
            print("")
            print("  Template - fill in real numbers, then paste into PowerShell:")
            print(f'  python -c "from team_stats_provider import upsert_soccer_team_stats; '
                  f'upsert_soccer_team_stats(\'{team}\', {{\'goals_for\': 0, \'goals_against\': 0}})"')
        else:
            print(f"  Search: https://www.euroleaguebasketball.net (or league\'s official stats page)")
            print("  Minimum needed: ortg, drtg (or recent_net if that\'s unavailable)")
            print("  Also check: injury_status, back_to_back, rest_days")
        print("")

    print("=" * 60)
    print("Once both teams show [ALREADY SEEDED] above, re-run this script")
    print("to confirm, then run the match through run_match_safe.py.")


if __name__ == "__main__":
    main()
