import json

from dotenv import load_dotenv

from universal_runner import push_to_discord


def main() -> None:
    load_dotenv()

    with open("output/tennis/Marta_Kostyuk_vs_Linda_Noskova.json", "r", encoding="utf-8") as f:
        result = json.load(f)

    moneyline = result.get("moneyline", {})
    total_games = result.get("total_games", {})

    home = moneyline.get("home", "Marta Kostyuk")
    away = moneyline.get("away", "Linda Noskova")

    edge = float(total_games.get("edge", 0.0))
    total_line = float(total_games.get("total_games_line", 22.5))
    recommendation = total_games.get("recommendation", "OVER 22.5")

    extra_metrics = (
        f"Tournament: {result.get('tournament', 'Wimbledon')} | "
        f"Home Win Prob: {float(moneyline.get('home_win_prob', 0.0)) * 100:.1f}% | "
        f"Away Win Prob: {float(moneyline.get('away_win_prob', 0.0)) * 100:.1f}% | "
        f"Sets Note: {result.get('sets', {}).get('recommendation', '')}"
    )

    ok = push_to_discord(
        sport="tennis",
        home=home,
        away=away,
        market_total=total_line,
        projected_total=total_line,
        edge=f"{edge:+.3f}",
        recommendation=recommendation,
        extra_metrics=extra_metrics,
    )

    print("DISCORD_PUSH_OK=", ok)


if __name__ == "__main__":
    main()
