"""Check which players from today's ATP Cincinnati matches are in the Elo model."""
import sys
import os

sys.path.insert(0, "c:/MultiSportPredict")
os.chdir("c:/MultiSportPredict")

from models.tennis_elo import TennisElo

elo = TennisElo()
elo.load_match_history()

players = [
    "Nuno Borges",
    "Andrey Rublev",
    "Lorenzo Musetti",
    "Michael Zheng",
    "Daniel Merida",
    "Taylor Fritz",
    "Daniil Medvedev",
    "Brandon Nakashima",
    "Adam Walton",
    "Jaime Faria",
    "Felix Auger-Aliassime",
    "Juan Manuel Cerundolo",
]

output = []
for p in players:
    r = elo.get_rating(p, "hard")
    mc = elo.get_match_count(p, "hard")
    output.append(f"{p}: rating={r:.0f}, matches={mc}")

with open("elo_coverage.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))
print("Written to elo_coverage.txt")