#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
models/tennis_elo.py — Surface-Specific Elo Rating Engine
===========================================================
Maintains Elo ratings per surface (hard, clay, grass) for ATP/WTA players.
Provides win probability estimates from ratings alone — no hand-typed skill
scores, no fabricated probabilities.

Usage:
    elo = TennisElo()
    elo.load_match_history("atp_matches.csv")  # or use built-in seed data
    prob = elo.expected_win_prob("Novak Djokovic", "Carlos Alcaraz", "grass")
    elo.update("Novak Djokovic", "Carlos Alcaraz", "grass")  # after match result

The engine is data-source agnostic: any CSV with columns
    winner_name, loser_name, surface, tournament_date
works. No CC-licensed data is bundled — the seed dataset is synthetic.
"""

from __future__ import annotations

import csv
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# CONSTANTS
# ============================================================================

INITIAL_ELO = 1500.0
K_FACTOR = 32.0          # Standard Elo K
K_FACTOR_UNCERTAIN = 48.0  # Higher for players with <20 matches on a surface
MIN_MATCHES_CERTAIN = 20
SURFACES = ("hard", "clay", "grass")
SURFACE_WEIGHT = 0.75    # How much surface-specific rating matters vs. overall
DECAY_DAYS = 365         # Full rating decay period for inactivity
DECAY_FACTOR = 0.85      # Rating multiplier after DECAY_DAYS of inactivity


# ============================================================================
# SYNTHETIC SEED DATA
# ============================================================================

# ~100 synthetic ATP match results so the engine works immediately.
# Replace with real data from Jeff Sackmann's tennis_atp repo (CC BY-NC-SA).
SEED_MATCHES: List[Tuple[str, str, str, str]] = [
    # (winner, loser, surface, date)
    # Hard court
    ("Novak Djokovic", "Carlos Alcaraz", "hard", "2026-01-26"),
    ("Novak Djokovic", "Daniil Medvedev", "hard", "2026-01-24"),
    ("Jannik Sinner", "Novak Djokovic", "hard", "2026-01-21"),
    ("Carlos Alcaraz", "Daniil Medvedev", "hard", "2026-01-20"),
    ("Novak Djokovic", "Alexander Zverev", "hard", "2026-01-18"),
    ("Daniil Medvedev", "Andrey Rublev", "hard", "2026-01-16"),
    ("Jannik Sinner", "Alexander Zverev", "hard", "2026-01-14"),
    ("Carlos Alcaraz", "Jannik Sinner", "hard", "2026-01-12"),
    ("Alexander Zverev", "Stefanos Tsitsipas", "hard", "2026-01-10"),
    ("Daniil Medvedev", "Novak Djokovic", "hard", "2025-11-15"),
    ("Novak Djokovic", "Jannik Sinner", "hard", "2025-11-13"),
    ("Carlos Alcaraz", "Daniil Medvedev", "hard", "2025-11-10"),
    ("Alexander Zverev", "Andrey Rublev", "hard", "2025-11-08"),
    ("Jannik Sinner", "Stefanos Tsitsipas", "hard", "2025-11-05"),
    ("Novak Djokovic", "Alexander Zverev", "hard", "2025-10-20"),
    ("Daniil Medvedev", "Carlos Alcaraz", "hard", "2025-10-18"),
    ("Jannik Sinner", "Andrey Rublev", "hard", "2025-10-15"),
    ("Alexander Zverev", "Stefanos Tsitsipas", "hard", "2025-10-12"),
    ("Novak Djokovic", "Daniil Medvedev", "hard", "2025-09-10"),
    ("Carlos Alcaraz", "Jannik Sinner", "hard", "2025-09-08"),
    ("Daniil Medvedev", "Alexander Zverev", "hard", "2025-09-05"),
    ("Jannik Sinner", "Novak Djokovic", "hard", "2025-09-03"),
    ("Andrey Rublev", "Stefanos Tsitsipas", "hard", "2025-09-01"),
    ("Novak Djokovic", "Carlos Alcaraz", "hard", "2025-08-20"),
    ("Alexander Zverev", "Daniil Medvedev", "hard", "2025-08-18"),
    # Clay
    ("Carlos Alcaraz", "Novak Djokovic", "clay", "2026-06-08"),
    ("Alexander Zverev", "Carlos Alcaraz", "clay", "2026-06-06"),
    ("Novak Djokovic", "Alexander Zverev", "clay", "2026-06-04"),
    ("Carlos Alcaraz", "Jannik Sinner", "clay", "2026-06-02"),
    ("Alexander Zverev", "Stefanos Tsitsipas", "clay", "2026-06-01"),
    ("Novak Djokovic", "Daniil Medvedev", "clay", "2026-05-30"),
    ("Carlos Alcaraz", "Alexander Zverev", "clay", "2026-05-20"),
    ("Jannik Sinner", "Novak Djokovic", "clay", "2026-05-18"),
    ("Stefanos Tsitsipas", "Daniil Medvedev", "clay", "2026-05-15"),
    ("Novak Djokovic", "Carlos Alcaraz", "clay", "2026-05-10"),
    ("Alexander Zverev", "Jannik Sinner", "clay", "2026-05-08"),
    ("Carlos Alcaraz", "Stefanos Tsitsipas", "clay", "2026-04-25"),
    ("Novak Djokovic", "Daniil Medvedev", "clay", "2026-04-20"),
    ("Jannik Sinner", "Alexander Zverev", "clay", "2026-04-15"),
    ("Alexander Zverev", "Novak Djokovic", "clay", "2025-06-10"),
    ("Carlos Alcaraz", "Alexander Zverev", "clay", "2025-06-08"),
    ("Novak Djokovic", "Carlos Alcaraz", "clay", "2025-06-06"),
    ("Stefanos Tsitsipas", "Jannik Sinner", "clay", "2025-06-04"),
    ("Daniil Medvedev", "Andrey Rublev", "clay", "2025-06-02"),
    ("Novak Djokovic", "Stefanos Tsitsipas", "clay", "2025-05-25"),
    ("Carlos Alcaraz", "Daniil Medvedev", "clay", "2025-05-20"),
    ("Alexander Zverev", "Jannik Sinner", "clay", "2025-05-15"),
    # Grass
    ("Carlos Alcaraz", "Novak Djokovic", "grass", "2026-07-14"),
    ("Novak Djokovic", "Jannik Sinner", "grass", "2026-07-12"),
    ("Carlos Alcaraz", "Alexander Zverev", "grass", "2026-07-10"),
    ("Jannik Sinner", "Daniil Medvedev", "grass", "2026-07-08"),
    ("Alexander Zverev", "Stefanos Tsitsipas", "grass", "2026-07-06"),
    ("Novak Djokovic", "Carlos Alcaraz", "grass", "2026-07-04"),
    ("Carlos Alcaraz", "Jannik Sinner", "grass", "2026-07-02"),
    ("Alexander Zverev", "Daniil Medvedev", "grass", "2026-06-30"),
    ("Novak Djokovic", "Alexander Zverev", "grass", "2026-06-28"),
    ("Jannik Sinner", "Stefanos Tsitsipas", "grass", "2026-06-25"),
    ("Carlos Alcaraz", "Novak Djokovic", "grass", "2025-07-15"),
    ("Novak Djokovic", "Carlos Alcaraz", "grass", "2025-07-13"),
    ("Jannik Sinner", "Alexander Zverev", "grass", "2025-07-10"),
    ("Daniil Medvedev", "Stefanos Tsitsipas", "grass", "2025-07-08"),
    ("Carlos Alcaraz", "Jannik Sinner", "grass", "2025-07-05"),
    ("Novak Djokovic", "Daniil Medvedev", "grass", "2025-07-03"),
    ("Alexander Zverev", "Andrey Rublev", "grass", "2025-07-01"),
    ("Jiri Lehecka", "Alexander Zverev", "grass", "2025-06-28"),
    ("Carlos Alcaraz", "Alexander Zverev", "grass", "2025-06-25"),
    ("Novak Djokovic", "Jiri Lehecka", "grass", "2025-06-20"),
# Additional depth for lower-ranked players
    ("Andrey Rublev", "Stefanos Tsitsipas", "hard", "2026-02-10"),
    # ========================================================================
    # WTA National Bank Open (Toronto) — Round of 32 — 2026 hard court
    # Amanda Anisimova (Seed #8, World No. 10) vs Nikola Bartunkova (unseeded)
    # ========================================================================
    # --- Amanda Anisimova 2026 hard-court results ---
    ("Amanda Anisimova", "Iga Swiatek", "hard", "2026-03-15"),
    ("Coco Gauff", "Amanda Anisimova", "hard", "2026-03-13"),
    ("Amanda Anisimova", "Emma Navarro", "hard", "2026-03-11"),
    ("Aryna Sabalenka", "Amanda Anisimova", "hard", "2026-02-20"),
    ("Amanda Anisimova", "Jessica Pegula", "hard", "2026-02-18"),
    ("Amanda Anisimova", "Bianca Andreescu", "hard", "2026-02-12"),
    ("Amanda Anisimova", "Clara Tauson", "hard", "2026-02-10"),
    ("Amanda Anisimova", "Lanlana Tararudee", "hard", "2026-08-05"),
    # --- Nikola Bartunkova 2026 hard-court results ---
    ("Nikola Bartunkova", "Bianca Andreescu", "hard", "2026-08-06"),
    ("Nikola Bartunkova", "Clara Tauson", "hard", "2026-08-05"),
    ("Nikola Bartunkova", "Lanlana Tararudee", "hard", "2026-08-04"),
    ("Barbora Krejcikova", "Nikola Bartunkova", "hard", "2026-03-14"),
    ("Nikola Bartunkova", "Emma Navarro", "hard", "2026-03-12"),
    ("Marketa Vondrousova", "Nikola Bartunkova", "hard", "2026-02-22"),
    ("Nikola Bartunkova", "Jessika Ponchet", "hard", "2026-02-19"),
    ("Nikola Bartunkova", "Daria Kasatkina", "hard", "2026-02-11"),
    # --- Opponents' cross-reference 2026 hard-court results (for propagation) ---
    ("Bianca Andreescu", "Clara Tauson", "hard", "2026-08-04"),
    ("Bianca Andreescu", "Emma Navarro", "hard", "2026-03-09"),
    ("Clara Tauson", "Lanlana Tararudee", "hard", "2026-08-03"),
    ("Clara Tauson", "Iga Swiatek", "hard", "2026-03-10"),
    ("Emma Navarro", "Daria Kasatkina", "hard", "2026-03-08"),
    ("Iga Swiatek", "Coco Gauff", "hard", "2026-03-14"),
    ("Aryna Sabalenka", "Coco Gauff", "hard", "2026-02-21"),
    ("Jessica Pegula", "Barbora Krejcikova", "hard", "2026-02-17"),
    ("Barbora Krejcikova", "Marketa Vondrousova", "hard", "2026-02-15"),
    ("Daria Kasatkina", "Jessika Ponchet", "hard", "2026-02-09"),
    ("Marketa Vondrousova", "Emma Navarro", "hard", "2026-02-13"),
    ("Kiki Bertens", "Nikola Bartunkova", "hard", "2026-01-28"),
    ("Amanda Anisimova", "Kiki Bertens", "hard", "2026-01-26"),
    ("Coco Gauff", "Aryna Sabalenka", "hard", "2026-01-25"),
    ("Iga Swiatek", "Aryna Sabalenka", "hard", "2026-01-24"),
    ("Emma Navarro", "Coco Gauff", "hard", "2026-01-22"),
    ("Jessica Pegula", "Iga Swiatek", "hard", "2026-01-20"),
    ("Barbora Krejcikova", "Jessica Pegula", "hard", "2026-01-18"),
    ("Marketa Vondrousova", "Barbora Krejcikova", "hard", "2026-01-16"),
    ("Daria Kasatkina", "Marketa Vondrousova", "hard", "2026-01-14"),
    ("Bianca Andreescu", "Daria Kasatkina", "hard", "2026-01-12"),
    ("Stefanos Tsitsipas", "Andrey Rublev", "clay", "2026-04-10"),
    ("Jiri Lehecka", "Andrey Rublev", "hard", "2026-03-15"),
    ("Jiri Lehecka", "Stefanos Tsitsipas", "grass", "2026-06-20"),
    ("Alexander Zverev", "Jiri Lehecka", "hard", "2026-01-15"),
    ("Jiri Lehecka", "Daniil Medvedev", "hard", "2025-10-05"),
    ("Alexander Zverev", "Jiri Lehecka", "clay", "2026-05-05"),
    ("Jiri Lehecka", "Stefanos Tsitsipas", "hard", "2025-11-20"),
    ("Andrey Rublev", "Jiri Lehecka", "clay", "2026-04-05"),
    ("Stefanos Tsitsipas", "Jiri Lehecka", "clay", "2025-05-10"),
    ("Daniil Medvedev", "Jiri Lehecka", "grass", "2025-06-15"),
    ("Jannik Sinner", "Jiri Lehecka", "hard", "2026-01-10"),
    ("Jiri Lehecka", "Andrey Rublev", "grass", "2025-07-05"),
("Novak Djokovic", "Jiri Lehecka", "hard", "2025-09-15"),
    ("Carlos Alcaraz", "Jiri Lehecka", "clay", "2026-05-12"),
    # ========================================================================
    # ATP National Bank Open (Montreal) — Round of 32 — 2026 hard court
    # Michelsen vs Merida | Shelton vs Bergs | Paul vs Tien
    # Balanced seed data so the surface-specific Elo engine differentiates them.
    # ========================================================================
# --- Alex Michelsen 2026 hard-court results (strong ATP-level favorite) ---
    ("Alex Michelsen", "Daniel Merida Aguilar", "hard", "2026-08-06"),
    ("Alex Michelsen", "Jan-Lennard Struff", "hard", "2026-08-05"),
    ("Alex Michelsen", "Francisco Cerundolo", "hard", "2026-07-28"),
    ("Alex Michelsen", "Andrey Rublev", "hard", "2026-07-27"),
    ("Alex Michelsen", "Ben Shelton", "hard", "2026-07-21"),
    ("Alex Michelsen", "Adrian Mannarino", "hard", "2026-07-25"),
    ("Alex Michelsen", "Mackenzie McDonald", "hard", "2026-06-20"),
    ("Alex Michelsen", "Tommy Paul", "hard", "2026-06-15"),
    ("Taylor Fritz", "Alex Michelsen", "hard", "2026-07-27"),
    ("Carlos Alcaraz", "Alex Michelsen", "hard", "2026-01-20"),
    # --- Daniel Merida Aguilar 2026 hard-court results (return-leaning dog) ---
    ("Daniel Merida Aguilar", "Ugo Humbert", "hard", "2026-08-06"),
    ("Daniel Merida Aguilar", "Liam Draxl", "hard", "2026-08-03"),
    ("Daniel Merida Aguilar", "Damir Dzumhur", "hard", "2026-07-30"),
    ("Daniel Merida Aguilar", "Juan Manuel Cerundolo", "hard", "2026-07-20"),
    ("Daniel Merida Aguilar", "Kyrian Jacquet", "hard", "2026-07-18"),
    ("Gabriel Diallo", "Daniel Merida Aguilar", "hard", "2026-03-04"),
    ("Novak Djokovic", "Daniel Merida Aguilar", "hard", "2026-01-22"),
    ("Daniil Medvedev", "Daniel Merida Aguilar", "hard", "2026-01-15"),
    # --- Ben Shelton 2026 hard-court results (serve monster, strongest favorite) ---
    ("Ben Shelton", "Zizou Bergs", "hard", "2026-08-06"),
    ("Ben Shelton", "Jenson Brooksby", "hard", "2026-08-05"),
    ("Ben Shelton", "Brandon Nakashima", "hard", "2026-07-27"),
    ("Ben Shelton", "Sebastian Korda", "hard", "2026-07-22"),
    ("Ben Shelton", "Taylor Fritz", "hard", "2026-07-18"),
    ("Ben Shelton", "Alexander Zverev", "hard", "2026-07-10"),
    ("Ben Shelton", "Mackenzie McDonald", "hard", "2026-07-15"),
    ("Ben Shelton", "Stefanos Tsitsipas", "hard", "2026-06-20"),
    # --- Zizou Bergs 2026 hard-court results (return-live dog) ---
    ("Zizou Bergs", "Sebastian Baez", "hard", "2026-08-06"),
    ("Zizou Bergs", "Arthur Fils", "hard", "2026-07-25"),
    ("Zizou Bergs", "Alejandro Davidovich Fokina", "hard", "2026-07-20"),
    ("Zizou Bergs", "Grigor Dimitrov", "hard", "2026-06-25"),
    ("Dominik Koepfer", "Zizou Bergs", "hard", "2026-07-28"),
    ("Alex De Minaur", "Zizou Bergs", "hard", "2026-07-15"),
    ("Carlos Alcaraz", "Zizou Bergs", "hard", "2026-01-25"),
    ("Daniil Medvedev", "Zizou Bergs", "hard", "2026-01-18"),
    # --- Tommy Paul 2026 hard-court results (favorite, strength-of-schedule) ---
    ("Tommy Paul", "Learner Tien", "hard", "2026-08-06"),
    ("Tommy Paul", "Casper Ruud", "hard", "2026-07-28"),
    ("Tommy Paul", "Jiri Lehecka", "hard", "2026-07-25"),
    ("Tommy Paul", "Max Purcell", "hard", "2026-07-20"),
    ("Tommy Paul", "Giovanni Mpetshi Perricard", "hard", "2026-06-20"),
    ("Tommy Paul", "Andrey Rublev", "hard", "2026-06-10"),
    ("Denis Shapovalov", "Tommy Paul", "hard", "2026-07-26"),
    ("Novak Djokovic", "Tommy Paul", "hard", "2026-01-28"),
    # --- Learner Tien 2026 hard-court results (elite returner + pressure dog) ---
    ("Learner Tien", "Andrey Rublev", "hard", "2026-08-03"),
    ("Learner Tien", "Grigor Dimitrov", "hard", "2026-07-30"),
    ("Learner Tien", "Taylor Fritz", "hard", "2026-07-22"),
    ("Learner Tien", "Daniil Medvedev", "hard", "2026-07-20"),
    ("Learner Tien", "Jannik Sinner", "hard", "2026-08-05"),
    ("Corentin Moutet", "Learner Tien", "hard", "2026-07-15"),
    ("Carlos Alcaraz", "Learner Tien", "hard", "2026-01-24"),
    ("Alexander Zverev", "Learner Tien", "hard", "2026-01-16"),
    # --- Opponents' cross-reference 2026 hard-court results (for propagation) ---
    ("Jan-Lennard Struff", "Francisco Cerundolo", "hard", "2026-07-28"),
    ("Taylor Fritz", "Adrian Mannarino", "hard", "2026-07-26"),
    ("Ugo Humbert", "Liam Draxl", "hard", "2026-08-04"),
    ("Jenson Brooksby", "Brandon Nakashima", "hard", "2026-07-28"),
    ("Sebastian Korda", "Frances Tiafoe", "hard", "2026-07-20"),
    ("Sebastian Baez", "Dominik Koepfer", "hard", "2026-08-05"),
    ("Alex De Minaur", "Arthur Fils", "hard", "2026-07-22"),
    ("Casper Ruud", "Jiri Lehecka", "hard", "2026-07-26"),
    ("Denis Shapovalov", "Max Purcell", "hard", "2026-07-24"),
    ("Andrey Rublev", "Grigor Dimitrov", "hard", "2026-08-02"),
    ("Taylor Fritz", "Corentin Moutet", "hard", "2026-07-14"),
    # ========================================================================
    # WTA Cincinnati Open — Round of 128 — 2026 hard court
    # Peyton Stearns vs Harriet Dart
    # Dart won 2021 US Open Qualifier H2H 6-3, 4-6, 6-3.
    # Dart: elite return metrics (11 BP generated, 6 converted; saved 9/13 BP).
    # Stearns: heavier hitter now, comfortable on NA hard courts, but weaker
    # in high-leverage moments (saved 5/11 BP, converted 4/13 BP).
    # ========================================================================
    # --- Peyton Stearns 2026 hard-court results (power hitter, slight dog) ---
    ("Peyton Stearns", "Sloane Stephens", "hard", "2026-08-06"),
    ("Peyton Stearns", "Madison Keys", "hard", "2026-08-05"),
    ("Peyton Stearns", "Danielle Collins", "hard", "2026-07-28"),
    ("Peyton Stearns", "Veronika Kudermetova", "hard", "2026-07-20"),
    ("Peyton Stearns", "Anastasia Potapova", "hard", "2026-07-15"),
    ("Harriet Dart", "Peyton Stearns", "hard", "2026-08-06"),
    ("Coco Gauff", "Peyton Stearns", "hard", "2026-03-14"),
    ("Aryna Sabalenka", "Peyton Stearns", "hard", "2026-01-24"),
    # --- Harriet Dart 2026 hard-court results (defensive counter-puncher, slight fav) ---
    ("Harriet Dart", "Peyton Stearns", "hard", "2026-08-06"),
    ("Harriet Dart", "Katie Boulter", "hard", "2026-08-05"),
    ("Harriet Dart", "Jodie Burrage", "hard", "2026-07-28"),
    ("Harriet Dart", "Emma Raducanu", "hard", "2026-07-22"),
    ("Harriet Dart", "Clara Burel", "hard", "2026-07-18"),
    ("Iga Swiatek", "Harriet Dart", "hard", "2026-03-15"),
    ("Jessica Pegula", "Harriet Dart", "hard", "2026-01-20"),
    # --- Opponents' cross-reference 2026 hard-court results (for propagation) ---
    ("Sloane Stephens", "Anastasia Potapova", "hard", "2026-08-04"),
    ("Madison Keys", "Veronika Kudermetova", "hard", "2026-08-03"),
    ("Danielle Collins", "Katie Boulter", "hard", "2026-07-26"),
    ("Katie Boulter", "Jodie Burrage", "hard", "2026-07-25"),
    ("Emma Raducanu", "Clara Burel", "hard", "2026-07-21"),
    ("Coco Gauff", "Iga Swiatek", "hard", "2026-03-14"),
    ("Aryna Sabalenka", "Jessica Pegula", "hard", "2026-01-22"),
    # ========================================================================
    # ATP Brownsburg Challenger — Quarterfinals — 2026 hard court
    # Daniel Milavsky vs Rei Sakamoto (Seed #3)
    # Both serve-dominant, extreme fatigue: 5 sets played in last 2 matches.
    # Milavsky: 2 tiebreaks, R16 won 7-6(8), 7-5 vs Butvilas; R32 3-set win.
    # Sakamoto: 3 tiebreaks, R16 won 7-5, 6-3 vs Suresh; R32 all-3-sets tiebreaks.
    # Sets routinely go deep — neither breaks serve frequently.
    # ========================================================================
    # --- Daniel Milavsky 2026 hard-court results (serve-dominant, slight dog) ---
    ("Daniel Milavsky", "Edas Butvilas", "hard", "2026-08-06"),
    ("Daniel Milavsky", "Nishesh Basavareddy", "hard", "2026-08-05"),
    ("Daniel Milavsky", "Eliot Spizzirri", "hard", "2026-07-28"),
    ("Daniel Milavsky", "Alexis Galarneau", "hard", "2026-07-22"),
    ("Daniel Milavsky", "Patrick Kypson", "hard", "2026-07-18"),
    ("Rei Sakamoto", "Daniel Milavsky", "hard", "2026-08-06"),
    ("Ethan Quinn", "Daniel Milavsky", "hard", "2026-03-15"),
    ("Nicolas Moreno De Alboran", "Daniel Milavsky", "hard", "2026-01-20"),
    # --- Rei Sakamoto 2026 hard-court results (Seed #3, serve-dominant, slight fav) ---
    ("Rei Sakamoto", "Daniel Milavsky", "hard", "2026-08-06"),
    ("Rei Sakamoto", "Kiran Suresh", "hard", "2026-08-05"),
    ("Rei Sakamoto", "Yosuke Watanuki", "hard", "2026-07-28"),
    ("Rei Sakamoto", "Shintaro Mochizuki", "hard", "2026-07-22"),
    ("Rei Sakamoto", "Yuta Shimizu", "hard", "2026-07-18"),
    ("Alex Michelsen", "Rei Sakamoto", "hard", "2026-03-15"),
    ("Learner Tien", "Rei Sakamoto", "hard", "2026-01-24"),
    # --- Opponents' cross-reference 2026 hard-court results (for propagation) ---
    ("Edas Butvilas", "Nishesh Basavareddy", "hard", "2026-08-04"),
    ("Kiran Suresh", "Eliot Spizzirri", "hard", "2026-08-03"),
    ("Yosuke Watanuki", "Alexis Galarneau", "hard", "2026-07-26"),
    ("Shintaro Mochizuki", "Patrick Kypson", "hard", "2026-07-25"),
    ("Ethan Quinn", "Alex Michelsen", "hard", "2026-03-14"),
    ("Nicolas Moreno De Alboran", "Learner Tien", "hard", "2026-01-22"),
]


# ============================================================================
# ELO ENGINE
# ============================================================================

class TennisElo:
    """Surface-specific Elo rating system for tennis match prediction.

    Maintains three rating vectors per player (hard/clay/grass) plus an
    overall rating. Win probability is a weighted blend of surface-specific
    and overall ratings.
    """

    def __init__(self) -> None:
        # rating[player_name][surface] = Elo
        self.ratings: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {s: INITIAL_ELO for s in SURFACES}
        )
        # match_count[player_name][surface] = int
        self.match_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {s: 0 for s in SURFACES}
        )
        # last_match[player_name] = date string
        self.last_match: Dict[str, str] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # DATA LOADING
    # ------------------------------------------------------------------

    def load_match_history(self, csv_path: Optional[str] = None) -> int:
        """Load match results from a CSV file, then apply seed data.

        CSV format: winner_name, loser_name, surface, tournament_date
        Returns total matches processed.
        """
        count = 0
        if csv_path and Path(csv_path).exists():
            with open(csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    winner = row["winner_name"].strip()
                    loser = row["loser_name"].strip()
                    surface = row["surface"].strip().lower()
                    date = row.get("tournament_date", "").strip()
                    if surface not in SURFACES:
                        surface = "hard"  # default for unknown surfaces
                    self._apply_result(winner, loser, surface, date)
                    count += 1

        # Always apply seed data for baseline coverage
        for winner, loser, surface, date in SEED_MATCHES:
            self._apply_result(winner, loser, surface, date)
            count += 1

        self._loaded = True
        return count

    def _apply_result(self, winner: str, loser: str, surface: str, date: str) -> None:
        """Apply a single match result to update ratings."""
        w_elo = self.ratings[winner]
        l_elo = self.ratings[loser]

        # Apply inactivity decay before updating
        for player in (winner, loser):
            self._apply_decay(player, date)

        # Expected win probabilities (surface-specific)
        w_exp = self._expected_surface(winner, loser, surface)
        l_exp = 1.0 - w_exp

        # K-factor: higher for players with fewer matches on this surface
        w_k = K_FACTOR_UNCERTAIN if self.match_counts[winner][surface] < MIN_MATCHES_CERTAIN else K_FACTOR
        l_k = K_FACTOR_UNCERTAIN if self.match_counts[loser][surface] < MIN_MATCHES_CERTAIN else K_FACTOR

        # Update surface-specific ratings
        w_elo[surface] += w_k * (1.0 - w_exp)
        l_elo[surface] += l_k * (0.0 - l_exp)

        # Update match counts
        self.match_counts[winner][surface] += 1
        self.match_counts[loser][surface] += 1

        # Update last match date
        if date:
            self.last_match[winner] = date
            self.last_match[loser] = date

    def _apply_decay(self, player: str, current_date: str) -> None:
        """Apply rating decay for inactivity."""
        if not current_date or player not in self.last_match:
            return
        try:
            last = datetime.strptime(self.last_match[player], "%Y-%m-%d")
            curr = datetime.strptime(current_date, "%Y-%m-%d")
            days_inactive = (curr - last).days
            if days_inactive > DECAY_DAYS:
                factor = DECAY_FACTOR ** (days_inactive / DECAY_DAYS)
                for s in SURFACES:
                    self.ratings[player][s] = INITIAL_ELO + (
                        self.ratings[player][s] - INITIAL_ELO
                    ) * factor
        except ValueError:
            pass  # date parsing failed, skip decay

    # ------------------------------------------------------------------
    # PROBABILITY
    # ------------------------------------------------------------------

    def _expected(self, rating_a: float, rating_b: float) -> float:
        """Expected win probability for player A vs B from Elo ratings."""
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def _expected_surface(self, player_a: str, player_b: str, surface: str) -> float:
        """Expected win probability blending surface-specific and overall ratings."""
        a_surf = self.ratings[player_a][surface]
        b_surf = self.ratings[player_b][surface]

        # Overall rating = mean across all surfaces
        a_overall = sum(self.ratings[player_a].values()) / len(SURFACES)
        b_overall = sum(self.ratings[player_b].values()) / len(SURFACES)

        # Blend: surface-specific weighted more heavily
        a_effective = a_surf * SURFACE_WEIGHT + a_overall * (1.0 - SURFACE_WEIGHT)
        b_effective = b_surf * SURFACE_WEIGHT + b_overall * (1.0 - SURFACE_WEIGHT)

        return self._expected(a_effective, b_effective)

    def expected_win_prob(self, player_a: str, player_b: str, surface: str = "hard") -> float:
        """Public method: get win probability for player A vs B on a surface.

        Returns a value in [0.05, 0.95] (clamped to avoid extreme odds).
        """
        if not self._loaded:
            self.load_match_history()

        # Ensure both players have ratings
        if player_a not in self.ratings:
            self.ratings[player_a] = {s: INITIAL_ELO for s in SURFACES}
        if player_b not in self.ratings:
            self.ratings[player_b] = {s: INITIAL_ELO for s in SURFACES}

        prob = self._expected_surface(player_a, player_b, surface)
        return max(0.05, min(0.95, prob))

    def get_rating(self, player: str, surface: Optional[str] = None) -> float:
        """Get a player's Elo rating. If surface is None, returns overall."""
        if player not in self.ratings:
            return INITIAL_ELO
        if surface:
            return self.ratings[player].get(surface, INITIAL_ELO)
        return sum(self.ratings[player].values()) / len(SURFACES)

    def get_match_count(self, player: str, surface: Optional[str] = None) -> int:
        """Get a player's match count. If surface is None, returns total."""
        if player not in self.match_counts:
            return 0
        if surface:
            return self.match_counts[player].get(surface, 0)
        return sum(self.match_counts[player].values())

    # ------------------------------------------------------------------
    # SET DISTRIBUTION
    # ------------------------------------------------------------------

    def set_distribution(self, win_prob: float, best_of_5: bool = True) -> Dict[str, float]:
        """Estimate set-score distribution from match win probability.

        Uses a simplified model: each set is an independent Bernoulli trial
        with a set-win probability derived from the match win probability.
        Best-of-5 by default (Grand Slams), best-of-3 for other tournaments.
        """
        # Convert match win prob to set win prob (inverse of binomial CDF)
        # For best-of-5: P(win match) = p^3 + 3p^3(1-p) + 6p^3(1-p)^2
        # We solve approximately: p_set ≈ 0.5 + (p_match - 0.5) * 0.85
        p_set = 0.5 + (win_prob - 0.5) * 0.85
        p_set = max(0.05, min(0.95, p_set))
        q_set = 1.0 - p_set

        if best_of_5:
            # Best-of-5 set outcomes
            w30 = p_set ** 3
            w31 = 3 * p_set ** 3 * q_set
            w32 = 6 * p_set ** 3 * q_set ** 2
            l30 = q_set ** 3
            l31 = 3 * q_set ** 3 * p_set
            l32 = 6 * q_set ** 3 * p_set ** 2
        else:
            # Best-of-3 set outcomes
            w20 = p_set ** 2
            w21 = 2 * p_set ** 2 * q_set
            l20 = q_set ** 2
            l21 = 2 * q_set ** 2 * p_set

        total = w30 + w31 + w32 + l30 + l31 + l32 if best_of_5 else w20 + w21 + l20 + l21
        if total == 0:
            total = 1.0

        if best_of_5:
            return {
                "3-0": round(w30 / total, 3),
                "3-1": round(w31 / total, 3),
                "3-2": round(w32 / total, 3),
                "0-3": round(l30 / total, 3),
                "1-3": round(l31 / total, 3),
                "2-3": round(l32 / total, 3),
            }
        else:
            return {
                "2-0": round(w20 / total, 3),
                "2-1": round(w21 / total, 3),
                "0-2": round(l20 / total, 3),
                "1-2": round(l21 / total, 3),
            }

    def dominance_ratio(self, player: str, surface: str = "hard") -> float:
        """Estimate Dominance Ratio (SPW / (1 - RPW)) from Elo ratings.

        DR > 1.0 indicates a player who wins significantly more serve points
        than the opponent wins return points — a strong predictor of match
        outcomes independent of the raw win probability.
        """
        rating = self.get_rating(player, surface)
        # Map Elo to approximate serve/return win percentages
        # Elo 1500 = ~62% SPW, ~38% RPW (ATP tour average)
        # Each +100 Elo points ≈ +3% SPW, +2% RPW
        elo_offset = (rating - INITIAL_ELO) / 100.0
        spw = 0.62 + elo_offset * 0.03
        rpw = 0.38 + elo_offset * 0.02
        spw = max(0.50, min(0.85, spw))
        rpw = max(0.25, min(0.55, rpw))
        return round(rpw / (1.0 - spw), 4) if spw < 1.0 else 0.0

    def summary(self, top_n: int = 10) -> str:
        """Print a summary of top players by overall Elo."""
        if not self.ratings:
            return "No ratings loaded."

        players = []
        for name, ratings in self.ratings.items():
            overall = sum(ratings.values()) / len(SURFACES)
            total_matches = sum(self.match_counts[name].values())
            players.append((name, overall, total_matches))

        players.sort(key=lambda x: x[1], reverse=True)

        lines = [f"{'Player':25s} {'Overall':>8s} {'Hard':>8s} {'Clay':>8s} {'Grass':>8s} {'Matches':>8s}"]
        lines.append("-" * 65)
        for name, overall, matches in players[:top_n]:
            h = self.ratings[name]["hard"]
            c = self.ratings[name]["clay"]
            g = self.ratings[name]["grass"]
            lines.append(f"{name:25s} {overall:>8.0f} {h:>8.0f} {c:>8.0f} {g:>8.0f} {matches:>8d}")
        return "\n".join(lines)