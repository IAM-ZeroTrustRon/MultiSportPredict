"""NBA/WNBA/NCAAB fixtures and international basketball metrics in one runner."""
import sys
from run_ncaaf import main

if __name__ == "__main__":
    values = sys.argv[1:]
    league = values[values.index("--league")+1] if "--league" in values else "NBA"
    league = {"NZ NBL": "NZNBL", "BUNDESLIGA": "BBL", "GERMAN BBL": "BBL"}.get(league.upper(), league.upper())
    if league.upper() in {"NBA", "WNBA", "NCAAB", "NCAAW"} or (league.upper() in {"KBL", "NZNBL", "BBL"} and "--home" not in values):
        main("basketball")
    else:
        from euroleague_engine import run_cli
        run_cli(values)
