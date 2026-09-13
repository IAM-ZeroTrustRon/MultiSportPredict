import argparse

try:
    import pandas as pd
    from pybaseball import playerid_lookup, statcast_batter
except ImportError as exc:
    raise SystemExit(
        f"Missing dependency: {exc.name}. Install required packages with 'pip install pandas pybaseball'."
    ) from exc


def get_player_hard_hit_data(
    first_name,
    last_name,
    start_date="2026-04-01",
    end_date="2026-05-27",
):
    """
    Scrapes historical Statcast data for a hitter and summarizes hard-hit capability.
    """
    try:
        ids = playerid_lookup(last_name, first_name)
        if ids is None or ids.empty:
            print(f"Error: Target entity resolve failed for {first_name} {last_name}")
            return None

        mlbam_id = ids.loc[0, "key_mlbam"]
        df = statcast_batter(start_date, end_date, mlbam_id)

        if df is None or df.empty:
            print(f"No batted ball event logs found for {first_name} {last_name}")
            return None

        required_cols = {"launch_speed", "launch_angle"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            print(f"Missing required Statcast columns for {first_name} {last_name}: {', '.join(sorted(missing_cols))}")
            return None

        batted_balls = df.loc[df["launch_speed"].notna()].copy()
        batted_balls["launch_speed"] = pd.to_numeric(batted_balls["launch_speed"], errors="coerce")
        batted_balls["launch_angle"] = pd.to_numeric(batted_balls["launch_angle"], errors="coerce")
        batted_balls = batted_balls.dropna(subset=["launch_speed", "launch_angle"])

        if batted_balls.empty:
            print(f"No valid launch metrics found for {first_name} {last_name}")
            return None

        hard_hit_count = int((batted_balls["launch_speed"] >= 95).sum())
        total_events = int(len(batted_balls))
        hard_hit_pct = (hard_hit_count / total_events) * 100 if total_events else 0.0

        return {
            "player_name": f"{first_name} {last_name}",
            "total_batted_balls": total_events,
            "statcast_hard_hit_pct": round(hard_hit_pct, 2),
            "raw_average_exit_velocity": round(float(batted_balls["launch_speed"].mean()), 2),
            "mean_launch_angle": round(float(batted_balls["launch_angle"].mean()), 2),
        }
    except Exception as exc:
        print(f"Pipeline error for parsing {first_name} {last_name}: {exc}")
        return None


def run_analysis(players=None, pitcher_hard_hit_allowed_pct=42.5):
    if players is None:
        players = [("Bryce", "Harper"), ("Trea", "Turner")]

    print("--- MODEL ANALYSIS: HARD-HIT DIFFERENTIAL MATRIX ---")
    for first_name, last_name in players:
        profile = get_player_hard_hit_data(first_name, last_name)
        if not profile:
            continue

        hh_differential = profile["statcast_hard_hit_pct"] - pitcher_hard_hit_allowed_pct

        print(f"\nTarget: {profile['player_name']}")
        print(f" -> Hitter Hard-Hit rate: {profile['statcast_hard_hit_pct']}%")
        print(f" -> Pitcher Hard-Hit Allowed rate: {pitcher_hard_hit_allowed_pct}%")
        print(f" -> CALCULATED HARD-HIT DIFFERENTIAL: {round(hh_differential, 2)}%")
        print(
            f" -> Raw Profile: Mean EV: {profile['raw_average_exit_velocity']} mph | LA: {profile['mean_launch_angle']}°"
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape Statcast hard-hit data for selected hitters and compare against a pitcher baseline."
    )
    parser.add_argument("--players", nargs="*", metavar=("FIRST", "LAST"), help="Optional player names (e.g. Bryce Harper)")
    parser.add_argument(
        "--pitcher-hard-hit-allowed",
        type=float,
        default=42.5,
        help="Hard-hit allowed baseline percentage for the pitcher (default: 42.5).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.players:
        if len(args.players) % 2 != 0:
            raise SystemExit("Provide player names as pairs: FIRST LAST FIRST LAST")
        player_pairs = []
        for idx in range(0, len(args.players), 2):
            player_pairs.append((args.players[idx], args.players[idx + 1]))
    else:
        player_pairs = [("Bryce", "Harper"), ("Trea", "Turner")]

    run_analysis(player_pairs, args.pitcher_hard_hit_allowed)


if __name__ == "__main__":
    main()
