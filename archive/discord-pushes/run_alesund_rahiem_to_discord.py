import sys

from run_soccer_to_discord import main as run_soccer_to_discord_main


def main() -> None:
    sys.argv = [
        "run_soccer_to_discord.py",
        "--home",
        "Alesund 2",
        "--away",
        "Rahiem 2",
    ]
    run_soccer_to_discord_main()


if __name__ == "__main__":
    main()
