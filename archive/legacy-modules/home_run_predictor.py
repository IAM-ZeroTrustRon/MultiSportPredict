import argparse

import pandas as pd
from pybaseball import playerid_lookup, statcast_batter


def get_player_power_profile(first_name, last_name, start_date="2026-04-01", end_date="2026-05-27"):
    ids = playerid_lookup(last_name, first_name)
    if ids is None or ids.empty:
        raise ValueError(f"Player lookup failed for {first_name} {last_name}")

    mlbam_id = ids.loc[0, "key_mlbam"]
    df = statcast_batter(start_date, end_date, mlbam_id)
    if df is None or df.empty:
        raise ValueError(f"No Statcast data found for {first_name} {last_name}")

    required_cols = {"launch_speed", "launch_angle"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns for {first_name} {last_name}: {', '.join(sorted(missing_cols))}")

    batted_balls = df.loc[df["launch_speed"].notna()].copy()
    batted_balls["launch_speed"] = pd.to_numeric(batted_balls["launch_speed"], errors="coerce")
    batted_balls["launch_angle"] = pd.to_numeric(batted_balls["launch_angle"], errors="coerce")
    batted_balls = batted_balls.dropna(subset=["launch_speed", "launch_angle"])

    if batted_balls.empty:
        raise ValueError(f"No valid launch metrics for {first_name} {last_name}")

    hard_hit_pct = float((batted_balls["launch_speed"] >= 95).mean() * 100)
    avg_exit_velocity = float(batted_balls["launch_speed"].mean())
    avg_launch_angle = float(batted_balls["launch_angle"].mean())

    sweet_spot_bonus = 0.0
    if 8 <= avg_launch_angle <= 32:
        sweet_spot_bonus = 10.0
    elif avg_launch_angle < 8:
        sweet_spot_bonus = max(0.0, 10.0 - (8 - avg_launch_angle) * 1.5)
    else:
        sweet_spot_bonus = max(0.0, 10.0 - (avg_launch_angle - 32) * 0.4)

    return {
        "player_name": f"{first_name} {last_name}",
        "hard_hit_pct": hard_hit_pct,
        "avg_exit_velocity": avg_exit_velocity,
        "avg_launch_angle": avg_launch_angle,
        "sweet_spot_bonus": sweet_spot_bonus,
    }


def score_player(profile):
    ev_component = min(profile["avg_exit_velocity"] / 100.0, 1.0) * 45
    hard_hit_component = min(profile["hard_hit_pct"] / 100.0, 1.0) * 35
    launch_component = min(profile["sweet_spot_bonus"] / 10.0, 1.0) * 20

    score = ev_component + hard_hit_component + launch_component
    projected_hr_pct = min((profile["hard_hit_pct"] * 0.55) + (profile["avg_exit_velocity"] * 0.25), 100.0)
    return {
        "player_name": profile["player_name"],
        "score": round(score, 2),
        "projected_hr_pct": round(projected_hr_pct, 2),
        "hard_hit_pct": profile["hard_hit_pct"],
        "avg_exit_velocity": profile["avg_exit_velocity"],
        "avg_launch_angle": profile["avg_launch_angle"],
    }


def top_home_run_hitters(players, top_n=5):
    scored = []
    for first_name, last_name in players:
        try:
            profile = get_player_power_profile(first_name, last_name)
            scored.append(score_player(profile))
        except ValueError as exc:
            print(exc)

    ranked = sorted(scored, key=lambda item: (item["score"], item["projected_hr_pct"]), reverse=True)
    return ranked[:top_n]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Rank hitters by a power-contact scoring model that emphasizes hard-hit rate, exit velocity, and launch-angle quality."
    )
    parser.add_argument(
        "--players",
        nargs="*",
        metavar=("FIRST", "LAST"),
        help="Optional player names (e.g. Bryce Harper).",
    )
    parser.add_argument("--top-n", type=int, default=5, help="Number of hitters to rank (default: 5).")
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
        player_pairs = [("Bryce", "Harper"), ("Trea", "Turner"), ("Aaron", "Judge")]

    ranked = top_home_run_hitters(player_pairs, top_n=args.top_n)

    print("Top Home Run Hitter Candidates")
    print("-" * 40)
    for idx, result in enumerate(ranked, start=1):
        print(
            f"{idx}. {result['player_name']} | Score: {result['score']} | Projected HR%: {result['projected_hr_pct']}%"
        )
        print(
            f"   Hard-hit%: {result['hard_hit_pct']:.2f}% | Avg EV: {result['avg_exit_velocity']:.2f} mph | Avg LA: {result['avg_launch_angle']:.2f}°"
        )


if __name__ == "__main__":
    main()
