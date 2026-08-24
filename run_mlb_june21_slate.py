#!/usr/bin/env python
"""
MLB FULL SLATE — JUNE 21, 2026 — ALL 15 GAMES
=================================================
Complete analysis: Moneyline, Run Line, Totals, NRFI/YRFI,
Pitcher Props, Hitter Props, Game Analysis.

Strong bets (>=65% confidence) → pushed to Discord
Medium/Pass → logged only

Run: python run_mlb_june21_slate.py
"""

from __future__ import annotations
import json, math, os, logging, sys
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename="mlb_june21_2026_analysis.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.WARNING)
log.addHandler(console)

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
DATE_LABEL = "June 21, 2026 (Sunday)"
TODAY = "2026-06-21"

# ─────────────────────────────────────────────────────────────────────────────
# PARK FACTORS  (run_factor >1 = hitter park)
# ─────────────────────────────────────────────────────────────────────────────
PARK = {
    "NYY": {"name": "Yankee Stadium",              "run": 1.02, "hr": 1.15},
    "ATL": {"name": "Truist Park",                 "run": 1.01, "hr": 1.03},
    "TB":  {"name": "Tropicana Field",             "run": 0.97, "hr": 0.94},
    "DET": {"name": "Comerica Park",               "run": 0.97, "hr": 0.93},
    "MIA": {"name": "loanDepot park",              "run": 0.98, "hr": 0.95},
    "HOU": {"name": "Daikin Park",                 "run": 1.02, "hr": 1.08},
    "KC":  {"name": "Kauffman Stadium",            "run": 1.00, "hr": 1.02},
    "CHC": {"name": "Wrigley Field",               "run": 1.01, "hr": 1.03},
    "TEX": {"name": "Globe Life Field",            "run": 1.01, "hr": 1.04},
    "COL": {"name": "Coors Field",                 "run": 1.18, "hr": 1.05},
    "ARI": {"name": "Chase Field",                 "run": 1.03, "hr": 1.06},
    "OAK": {"name": "Sutter Health Park",          "run": 0.94, "hr": 0.90},
    "LAD": {"name": "UNIQLO Field @ Dodger Std",   "run": 0.99, "hr": 0.95},
    "SEA": {"name": "T-Mobile Park",               "run": 0.97, "hr": 0.95},
    "PHI": {"name": "Citizens Bank Park",          "run": 1.04, "hr": 1.10},
}

# ─────────────────────────────────────────────────────────────────────────────
# TEAM STATS  (2026 season through June 21)
# rpg = runs/game offensive   ra_g = runs allowed/game
# ─────────────────────────────────────────────────────────────────────────────
TEAM = {
    "CIN": {"rpg": 4.3, "ra_g": 4.6, "name": "Cincinnati Reds",         "abbr": "CIN"},
    "NYY": {"rpg": 5.2, "ra_g": 4.1, "name": "New York Yankees",        "abbr": "NYY"},
    "MIL": {"rpg": 4.2, "ra_g": 3.9, "name": "Milwaukee Brewers",       "abbr": "MIL"},
    "ATL": {"rpg": 5.0, "ra_g": 4.3, "name": "Atlanta Braves",          "abbr": "ATL"},
    "WSH": {"rpg": 4.0, "ra_g": 4.8, "name": "Washington Nationals",    "abbr": "WSH"},
    "TB":  {"rpg": 4.1, "ra_g": 4.0, "name": "Tampa Bay Rays",          "abbr": "TB"},
    "CWS": {"rpg": 3.6, "ra_g": 5.1, "name": "Chicago White Sox",       "abbr": "CWS"},
    "DET": {"rpg": 4.3, "ra_g": 4.3, "name": "Detroit Tigers",          "abbr": "DET"},
    "SF":  {"rpg": 4.2, "ra_g": 4.0, "name": "San Francisco Giants",    "abbr": "SF"},
    "MIA": {"rpg": 3.8, "ra_g": 4.5, "name": "Miami Marlins",           "abbr": "MIA"},
    "CLE": {"rpg": 4.2, "ra_g": 3.8, "name": "Cleveland Guardians",     "abbr": "CLE"},
    "HOU": {"rpg": 4.7, "ra_g": 4.0, "name": "Houston Astros",          "abbr": "HOU"},
    "STL": {"rpg": 4.2, "ra_g": 4.4, "name": "St. Louis Cardinals",     "abbr": "STL"},
    "KC":  {"rpg": 4.4, "ra_g": 4.2, "name": "Kansas City Royals",      "abbr": "KC"},
    "TOR": {"rpg": 4.4, "ra_g": 4.4, "name": "Toronto Blue Jays",       "abbr": "TOR"},
    "CHC": {"rpg": 4.6, "ra_g": 4.2, "name": "Chicago Cubs",            "abbr": "CHC"},
    "SD":  {"rpg": 4.2, "ra_g": 3.9, "name": "San Diego Padres",        "abbr": "SD"},
    "TEX": {"rpg": 4.5, "ra_g": 4.2, "name": "Texas Rangers",           "abbr": "TEX"},
    "PIT": {"rpg": 4.0, "ra_g": 4.4, "name": "Pittsburgh Pirates",      "abbr": "PIT"},
    "COL": {"rpg": 4.5, "ra_g": 5.2, "name": "Colorado Rockies",        "abbr": "COL"},
    "MIN": {"rpg": 4.4, "ra_g": 4.2, "name": "Minnesota Twins",         "abbr": "MIN"},
    "ARI": {"rpg": 4.5, "ra_g": 4.3, "name": "Arizona Diamondbacks",    "abbr": "ARI"},
    "LAA": {"rpg": 4.1, "ra_g": 4.7, "name": "Los Angeles Angels",      "abbr": "LAA"},
    "OAK": {"rpg": 3.9, "ra_g": 4.8, "name": "Athletics",               "abbr": "OAK"},
    "BAL": {"rpg": 4.6, "ra_g": 4.4, "name": "Baltimore Orioles",       "abbr": "BAL"},
    "LAD": {"rpg": 5.1, "ra_g": 3.9, "name": "Los Angeles Dodgers",     "abbr": "LAD"},
    "BOS": {"rpg": 4.8, "ra_g": 4.3, "name": "Boston Red Sox",          "abbr": "BOS"},
    "SEA": {"rpg": 4.1, "ra_g": 3.7, "name": "Seattle Mariners",        "abbr": "SEA"},
    "NYM": {"rpg": 4.4, "ra_g": 4.0, "name": "New York Mets",           "abbr": "NYM"},
    "PHI": {"rpg": 4.9, "ra_g": 4.1, "name": "Philadelphia Phillies",   "abbr": "PHI"},
}

# ─────────────────────────────────────────────────────────────────────────────
# PITCHER DATA  (era, k9, bb9, ip_proj = projected IP today)
# nrfi_rate = historical rate of not allowing a run in 1st inning (0-1)
# ─────────────────────────────────────────────────────────────────────────────
PITCHERS = {
    "Chase Burns":          {"era": 4.05, "k9": 9.5,  "bb9": 3.5, "ip": 5.2, "nrfi_rate": 0.70, "hand": "R"},
    "Elmer Rodriguez-Lopez":{"era": 5.10, "k9": 8.5,  "bb9": 3.8, "ip": 4.2, "nrfi_rate": 0.60, "hand": "R"},
    "Robert Gasser":        {"era": 3.90, "k9": 8.5,  "bb9": 3.0, "ip": 5.0, "nrfi_rate": 0.72, "hand": "L"},
    "Bryce Elder":          {"era": 4.30, "k9": 7.5,  "bb9": 3.0, "ip": 5.1, "nrfi_rate": 0.68, "hand": "R"},
    "Andrew Alvarez":       {"era": 5.20, "k9": 7.5,  "bb9": 3.8, "ip": 4.5, "nrfi_rate": 0.62, "hand": "L"},
    "Nick Martinez":        {"era": 4.15, "k9": 7.5,  "bb9": 2.5, "ip": 5.2, "nrfi_rate": 0.70, "hand": "R"},
    "Davis Martin":         {"era": 4.75, "k9": 7.5,  "bb9": 3.5, "ip": 4.2, "nrfi_rate": 0.63, "hand": "R"},
    "Keider Montero":       {"era": 4.35, "k9": 8.5,  "bb9": 3.5, "ip": 5.0, "nrfi_rate": 0.66, "hand": "R"},
    "Logan Webb":           {"era": 2.90, "k9": 8.5,  "bb9": 2.0, "ip": 6.0, "nrfi_rate": 0.79, "hand": "R"},
    "Ryan Gusto":           {"era": 5.40, "k9": 7.0,  "bb9": 4.0, "ip": 3.2, "nrfi_rate": 0.58, "hand": "R"},
    "Slade Cecconi":        {"era": 4.55, "k9": 8.0,  "bb9": 3.5, "ip": 4.2, "nrfi_rate": 0.64, "hand": "R"},
    "Kai-Wei Teng":         {"era": 4.65, "k9": 7.5,  "bb9": 3.5, "ip": 4.0, "nrfi_rate": 0.62, "hand": "R"},
    "Dustin May":           {"era": 4.30, "k9": 8.5,  "bb9": 2.5, "ip": 5.1, "nrfi_rate": 0.68, "hand": "R"},
    "Stephen Kolek":        {"era": 4.55, "k9": 7.5,  "bb9": 3.2, "ip": 4.2, "nrfi_rate": 0.64, "hand": "R"},
    "Dylan Cease":          {"era": 2.95, "k9": 11.5, "bb9": 3.5, "ip": 6.0, "nrfi_rate": 0.76, "hand": "R"},
    "Shota Imanaga":        {"era": 2.80, "k9": 9.5,  "bb9": 2.0, "ip": 6.1, "nrfi_rate": 0.80, "hand": "L"},
    "Wandy Peralta":        {"era": 5.50, "k9": 7.5,  "bb9": 4.0, "ip": 3.0, "nrfi_rate": 0.58, "hand": "L"},
    "Nathan Eovaldi":       {"era": 4.10, "k9": 8.5,  "bb9": 2.5, "ip": 5.2, "nrfi_rate": 0.70, "hand": "R"},
    "Jared Jones":          {"era": 3.85, "k9": 10.0, "bb9": 3.5, "ip": 5.2, "nrfi_rate": 0.70, "hand": "R"},
    "Michael Lorenzen":     {"era": 5.80, "k9": 7.0,  "bb9": 2.5, "ip": 4.2, "nrfi_rate": 0.60, "hand": "R"},
    "Mike Paredes":         {"era": 4.75, "k9": 7.5,  "bb9": 3.5, "ip": 4.2, "nrfi_rate": 0.63, "hand": "R"},
    "Jose Cabrera":         {"era": 4.90, "k9": 7.5,  "bb9": 4.0, "ip": 3.2, "nrfi_rate": 0.60, "hand": "R"},
    "Reid Detmers":         {"era": 4.00, "k9": 9.5,  "bb9": 3.5, "ip": 5.1, "nrfi_rate": 0.70, "hand": "L"},
    "Jack Perkins":         {"era": 4.65, "k9": 7.0,  "bb9": 3.5, "ip": 4.2, "nrfi_rate": 0.63, "hand": "R"},
    "Brandon Young":        {"era": 5.40, "k9": 8.0,  "bb9": 4.0, "ip": 4.0, "nrfi_rate": 0.60, "hand": "R"},
    "Emmet Sheehan":        {"era": 3.90, "k9": 10.5, "bb9": 3.5, "ip": 5.1, "nrfi_rate": 0.71, "hand": "R"},
    "Payton Tolle":         {"era": 4.50, "k9": 8.0,  "bb9": 3.0, "ip": 4.2, "nrfi_rate": 0.65, "hand": "R"},
    "Logan Gilbert":        {"era": 3.20, "k9": 9.5,  "bb9": 2.0, "ip": 6.1, "nrfi_rate": 0.78, "hand": "R"},
    "David Peterson":       {"era": 3.80, "k9": 9.5,  "bb9": 2.5, "ip": 5.2, "nrfi_rate": 0.72, "hand": "L"},
    "Zack Wheeler":         {"era": 3.00, "k9": 11.0, "bb9": 1.8, "ip": 6.1, "nrfi_rate": 0.81, "hand": "R"},
}

# ─────────────────────────────────────────────────────────────────────────────
# TOP HITTERS PER TEAM  (avg, hr_rate per AB, rbi_rate per game)
# ops = on-base+slugging proxy
# ─────────────────────────────────────────────────────────────────────────────
HITTERS = {
    "NYY": [
        {"name": "Aaron Judge",       "pos": "RF", "avg": .295, "ops": .980, "hr_rate": 0.12, "hits_avg": 1.2, "rbi_avg": 0.9},
        {"name": "Juan Soto",         "pos": "LF", "avg": .290, "ops": .950, "hr_rate": 0.08, "hits_avg": 1.1, "rbi_avg": 0.7},
        {"name": "Jazz Chisholm Jr.", "pos": "2B", "avg": .265, "ops": .820, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Giancarlo Stanton", "pos": "DH", "avg": .250, "ops": .840, "hr_rate": 0.09, "hits_avg": 0.9, "rbi_avg": 0.8},
    ],
    "CIN": [
        {"name": "Elly De La Cruz",   "pos": "SS", "avg": .270, "ops": .825, "hr_rate": 0.07, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "TJ Friedl",         "pos": "CF", "avg": .275, "ops": .810, "hr_rate": 0.04, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "Spencer Steer",     "pos": "3B", "avg": .255, "ops": .790, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Tyler Stephenson",  "pos": "C",  "avg": .260, "ops": .780, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.5},
    ],
    "ATL": [
        {"name": "Ronald Acuña Jr.",  "pos": "RF", "avg": .300, "ops": .950, "hr_rate": 0.07, "hits_avg": 1.2, "rbi_avg": 0.7},
        {"name": "Matt Olson",        "pos": "1B", "avg": .255, "ops": .870, "hr_rate": 0.09, "hits_avg": 1.0, "rbi_avg": 0.9},
        {"name": "Austin Riley",      "pos": "3B", "avg": .265, "ops": .860, "hr_rate": 0.08, "hits_avg": 1.0, "rbi_avg": 0.7},
        {"name": "Marcell Ozuna",     "pos": "DH", "avg": .270, "ops": .850, "hr_rate": 0.08, "hits_avg": 1.0, "rbi_avg": 0.8},
    ],
    "MIL": [
        {"name": "Christian Yelich",  "pos": "LF", "avg": .280, "ops": .875, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "Jackson Chourio",   "pos": "CF", "avg": .272, "ops": .820, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "William Contreras", "pos": "C",  "avg": .275, "ops": .830, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Rhys Hoskins",      "pos": "1B", "avg": .255, "ops": .820, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.7},
    ],
    "TB": [
        {"name": "Yandy Diaz",        "pos": "1B", "avg": .288, "ops": .830, "hr_rate": 0.03, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "Brandon Lowe",      "pos": "2B", "avg": .252, "ops": .810, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Isaac Paredes",     "pos": "3B", "avg": .242, "ops": .800, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Jose Siri",         "pos": "CF", "avg": .240, "ops": .745, "hr_rate": 0.05, "hits_avg": 0.8, "rbi_avg": 0.4},
    ],
    "WSH": [
        {"name": "CJ Abrams",         "pos": "SS", "avg": .272, "ops": .795, "hr_rate": 0.04, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "James Wood",        "pos": "CF", "avg": .268, "ops": .820, "hr_rate": 0.05, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Dylan Crews",       "pos": "RF", "avg": .262, "ops": .800, "hr_rate": 0.04, "hits_avg": 1.0, "rbi_avg": 0.4},
        {"name": "Luis Garcia Jr.",   "pos": "2B", "avg": .255, "ops": .760, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "DET": [
        {"name": "Riley Greene",      "pos": "LF", "avg": .275, "ops": .840, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "Kerry Carpenter",   "pos": "RF", "avg": .268, "ops": .825, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Colt Keith",        "pos": "2B", "avg": .258, "ops": .770, "hr_rate": 0.04, "hits_avg": 1.0, "rbi_avg": 0.4},
        {"name": "Zach McKinstry",    "pos": "3B", "avg": .248, "ops": .755, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "CWS": [
        {"name": "Luis Robert Jr.",   "pos": "CF", "avg": .268, "ops": .815, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Andrew Vaughn",     "pos": "1B", "avg": .255, "ops": .790, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Colson Montgomery", "pos": "SS", "avg": .245, "ops": .745, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
        {"name": "Lenyn Sosa",        "pos": "2B", "avg": .240, "ops": .720, "hr_rate": 0.03, "hits_avg": 0.8, "rbi_avg": 0.3},
    ],
    "SF": [
        {"name": "Matt Chapman",      "pos": "3B", "avg": .255, "ops": .810, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Heliot Ramos",      "pos": "RF", "avg": .265, "ops": .815, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Wilmer Flores",     "pos": "1B", "avg": .262, "ops": .790, "hr_rate": 0.05, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Mike Yastrzemski",  "pos": "LF", "avg": .250, "ops": .780, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "MIA": [
        {"name": "Luis Arraez",       "pos": "2B", "avg": .325, "ops": .830, "hr_rate": 0.01, "hits_avg": 1.3, "rbi_avg": 0.4},
        {"name": "Jake Burger",       "pos": "DH", "avg": .248, "ops": .790, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Kyle Stowers",      "pos": "LF", "avg": .258, "ops": .790, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.4},
        {"name": "Griffin Conine",    "pos": "RF", "avg": .245, "ops": .765, "hr_rate": 0.05, "hits_avg": 0.8, "rbi_avg": 0.4},
    ],
    "HOU": [
        {"name": "Yordan Alvarez",    "pos": "DH", "avg": .295, "ops": .970, "hr_rate": 0.10, "hits_avg": 1.1, "rbi_avg": 0.9},
        {"name": "Jose Altuve",       "pos": "2B", "avg": .285, "ops": .860, "hr_rate": 0.05, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "Jeremy Peña",       "pos": "SS", "avg": .268, "ops": .790, "hr_rate": 0.05, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Alex Bregman",      "pos": "3B", "avg": .260, "ops": .830, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.6},
    ],
    "CLE": [
        {"name": "Jose Ramirez",      "pos": "3B", "avg": .285, "ops": .900, "hr_rate": 0.08, "hits_avg": 1.1, "rbi_avg": 0.8},
        {"name": "Steven Kwan",       "pos": "LF", "avg": .290, "ops": .855, "hr_rate": 0.03, "hits_avg": 1.2, "rbi_avg": 0.4},
        {"name": "Josh Naylor",       "pos": "1B", "avg": .262, "ops": .820, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.7},
        {"name": "Tyler Freeman",     "pos": "2B", "avg": .258, "ops": .775, "hr_rate": 0.02, "hits_avg": 1.0, "rbi_avg": 0.4},
    ],
    "STL": [
        {"name": "Nolan Arenado",     "pos": "3B", "avg": .270, "ops": .835, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.7},
        {"name": "Lars Nootbaar",     "pos": "RF", "avg": .265, "ops": .820, "hr_rate": 0.05, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Paul Goldschmidt",  "pos": "1B", "avg": .268, "ops": .840, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Alec Burleson",     "pos": "LF", "avg": .258, "ops": .800, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.5},
    ],
    "KC": [
        {"name": "Bobby Witt Jr.",    "pos": "SS", "avg": .308, "ops": .920, "hr_rate": 0.07, "hits_avg": 1.3, "rbi_avg": 0.7},
        {"name": "Salvador Perez",    "pos": "C",  "avg": .268, "ops": .800, "hr_rate": 0.08, "hits_avg": 1.0, "rbi_avg": 0.7},
        {"name": "Vinnie Pasquantino","pos": "1B", "avg": .278, "ops": .855, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "MJ Melendez",       "pos": "LF", "avg": .248, "ops": .780, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
    ],
    "TOR": [
        {"name": "Vladimir Guerrero Jr.","pos": "1B", "avg": .298, "ops": .910, "hr_rate": 0.08, "hits_avg": 1.2, "rbi_avg": 0.7},
        {"name": "Bo Bichette",       "pos": "SS", "avg": .272, "ops": .810, "hr_rate": 0.05, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "George Springer",   "pos": "CF", "avg": .258, "ops": .810, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Daulton Varsho",    "pos": "LF", "avg": .248, "ops": .785, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
    ],
    "CHC": [
        {"name": "Dansby Swanson",    "pos": "SS", "avg": .255, "ops": .790, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Cody Bellinger",    "pos": "CF", "avg": .268, "ops": .830, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Ian Happ",          "pos": "LF", "avg": .255, "ops": .820, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Kyle Tucker",       "pos": "RF", "avg": .275, "ops": .875, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.7},
    ],
    "SD": [
        {"name": "Fernando Tatis Jr.","pos": "SS", "avg": .278, "ops": .890, "hr_rate": 0.08, "hits_avg": 1.1, "rbi_avg": 0.7},
        {"name": "Manny Machado",     "pos": "3B", "avg": .270, "ops": .845, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Jake Cronenworth",  "pos": "1B", "avg": .260, "ops": .800, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "Luis Campusano",    "pos": "C",  "avg": .262, "ops": .775, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "TEX": [
        {"name": "Corey Seager",      "pos": "SS", "avg": .278, "ops": .875, "hr_rate": 0.08, "hits_avg": 1.1, "rbi_avg": 0.7},
        {"name": "Marcus Semien",     "pos": "2B", "avg": .258, "ops": .810, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Adolis Garcia",     "pos": "RF", "avg": .252, "ops": .795, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Wyatt Langford",    "pos": "LF", "avg": .265, "ops": .820, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.5},
    ],
    "PIT": [
        {"name": "Oneil Cruz",        "pos": "SS", "avg": .258, "ops": .810, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Ke'Bryan Hayes",    "pos": "3B", "avg": .255, "ops": .780, "hr_rate": 0.03, "hits_avg": 1.0, "rbi_avg": 0.4},
        {"name": "Rowdy Tellez",      "pos": "1B", "avg": .248, "ops": .800, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Edward Olivares",   "pos": "RF", "avg": .250, "ops": .760, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "COL": [
        {"name": "Ryan McMahon",      "pos": "3B", "avg": .260, "ops": .800, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Brendan Rodgers",   "pos": "2B", "avg": .265, "ops": .790, "hr_rate": 0.04, "hits_avg": 1.0, "rbi_avg": 0.4},
        {"name": "Charlie Blackmon",  "pos": "RF", "avg": .252, "ops": .775, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
        {"name": "Nolan Jones",       "pos": "LF", "avg": .255, "ops": .800, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.5},
    ],
    "MIN": [
        {"name": "Carlos Correa",     "pos": "SS", "avg": .268, "ops": .825, "hr_rate": 0.06, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Byron Buxton",      "pos": "CF", "avg": .265, "ops": .850, "hr_rate": 0.08, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Royce Lewis",       "pos": "3B", "avg": .270, "ops": .840, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Ryan Jeffers",      "pos": "C",  "avg": .248, "ops": .790, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.5},
    ],
    "ARI": [
        {"name": "Corbin Carroll",    "pos": "LF", "avg": .278, "ops": .855, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "Ketel Marte",       "pos": "2B", "avg": .285, "ops": .870, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "Christian Walker",  "pos": "1B", "avg": .255, "ops": .820, "hr_rate": 0.07, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Lourdes Gurriel Jr.","pos": "RF", "avg": .268, "ops": .810, "hr_rate": 0.05, "hits_avg": 1.0, "rbi_avg": 0.5},
    ],
    "LAA": [
        {"name": "Mike Trout",        "pos": "CF", "avg": .275, "ops": .920, "hr_rate": 0.09, "hits_avg": 1.0, "rbi_avg": 0.7},
        {"name": "Taylor Ward",       "pos": "RF", "avg": .258, "ops": .790, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.4},
        {"name": "Zach Neto",         "pos": "SS", "avg": .258, "ops": .790, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.4},
        {"name": "Logan O'Hoppe",     "pos": "C",  "avg": .255, "ops": .775, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "OAK": [
        {"name": "Brent Rooker",      "pos": "DH", "avg": .260, "ops": .840, "hr_rate": 0.08, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "Lawrence Butler",   "pos": "LF", "avg": .252, "ops": .780, "hr_rate": 0.06, "hits_avg": 0.9, "rbi_avg": 0.5},
        {"name": "JJ Bleday",         "pos": "RF", "avg": .245, "ops": .760, "hr_rate": 0.05, "hits_avg": 0.8, "rbi_avg": 0.4},
        {"name": "Nick Allen",        "pos": "2B", "avg": .238, "ops": .695, "hr_rate": 0.02, "hits_avg": 0.8, "rbi_avg": 0.3},
    ],
    "BAL": [
        {"name": "Gunnar Henderson",  "pos": "SS", "avg": .278, "ops": .890, "hr_rate": 0.09, "hits_avg": 1.1, "rbi_avg": 0.7},
        {"name": "Cedric Mullins",    "pos": "CF", "avg": .262, "ops": .795, "hr_rate": 0.05, "hits_avg": 1.0, "rbi_avg": 0.4},
        {"name": "Anthony Santander", "pos": "RF", "avg": .262, "ops": .820, "hr_rate": 0.08, "hits_avg": 1.0, "rbi_avg": 0.6},
        {"name": "Ryan Mountcastle",  "pos": "1B", "avg": .265, "ops": .810, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.6},
    ],
    "LAD": [
        {"name": "Shohei Ohtani",     "pos": "DH", "avg": .305, "ops": 1.050,"hr_rate": 0.11, "hits_avg": 1.2, "rbi_avg": 1.0},
        {"name": "Freddie Freeman",   "pos": "1B", "avg": .298, "ops": .930, "hr_rate": 0.07, "hits_avg": 1.2, "rbi_avg": 0.8},
        {"name": "Mookie Betts",      "pos": "RF", "avg": .285, "ops": .900, "hr_rate": 0.07, "hits_avg": 1.1, "rbi_avg": 0.7},
        {"name": "Will Smith",        "pos": "C",  "avg": .268, "ops": .845, "hr_rate": 0.07, "hits_avg": 1.0, "rbi_avg": 0.6},
    ],
    "BOS": [
        {"name": "Rafael Devers",     "pos": "3B", "avg": .278, "ops": .890, "hr_rate": 0.08, "hits_avg": 1.1, "rbi_avg": 0.8},
        {"name": "Triston Casas",     "pos": "1B", "avg": .255, "ops": .840, "hr_rate": 0.08, "hits_avg": 0.9, "rbi_avg": 0.7},
        {"name": "Jarren Duran",      "pos": "CF", "avg": .280, "ops": .840, "hr_rate": 0.05, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "Alex Verdugo",      "pos": "LF", "avg": .265, "ops": .795, "hr_rate": 0.04, "hits_avg": 1.0, "rbi_avg": 0.4},
    ],
    "SEA": [
        {"name": "Julio Rodriguez",   "pos": "CF", "avg": .275, "ops": .855, "hr_rate": 0.07, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "Cal Raleigh",       "pos": "C",  "avg": .242, "ops": .820, "hr_rate": 0.09, "hits_avg": 0.9, "rbi_avg": 0.6},
        {"name": "JP Crawford",       "pos": "SS", "avg": .252, "ops": .760, "hr_rate": 0.04, "hits_avg": 0.9, "rbi_avg": 0.4},
        {"name": "Eugenio Suárez",    "pos": "3B", "avg": .240, "ops": .775, "hr_rate": 0.07, "hits_avg": 0.8, "rbi_avg": 0.6},
    ],
    "NYM": [
        {"name": "Francisco Lindor",  "pos": "SS", "avg": .280, "ops": .870, "hr_rate": 0.07, "hits_avg": 1.1, "rbi_avg": 0.6},
        {"name": "Pete Alonso",       "pos": "1B", "avg": .255, "ops": .855, "hr_rate": 0.10, "hits_avg": 0.9, "rbi_avg": 0.8},
        {"name": "Starling Marte",    "pos": "RF", "avg": .268, "ops": .800, "hr_rate": 0.04, "hits_avg": 1.0, "rbi_avg": 0.5},
        {"name": "Brandon Nimmo",     "pos": "LF", "avg": .258, "ops": .800, "hr_rate": 0.05, "hits_avg": 0.9, "rbi_avg": 0.4},
    ],
    "PHI": [
        {"name": "Bryce Harper",      "pos": "1B", "avg": .295, "ops": .970, "hr_rate": 0.08, "hits_avg": 1.2, "rbi_avg": 0.8},
        {"name": "Trea Turner",       "pos": "SS", "avg": .282, "ops": .840, "hr_rate": 0.05, "hits_avg": 1.1, "rbi_avg": 0.5},
        {"name": "Kyle Schwarber",    "pos": "LF", "avg": .242, "ops": .860, "hr_rate": 0.10, "hits_avg": 0.8, "rbi_avg": 0.7},
        {"name": "Alec Bohm",         "pos": "3B", "avg": .278, "ops": .825, "hr_rate": 0.06, "hits_avg": 1.1, "rbi_avg": 0.6},
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# 15-GAME SLATE
# ─────────────────────────────────────────────────────────────────────────────
SLATE = [
    {
        "game": "CIN @ NYY", "time_et": "1:35 PM ET", "away": "CIN", "home": "NYY",
        "away_sp": "Chase Burns", "home_sp": "Elmer Rodriguez-Lopez",
        "market_total": 8.5, "market_ml_home": -220, "market_ml_away": 185,
        "weather": "Indoor/Outdoor (open air)", "wind": "8 mph in",
    },
    {
        "game": "MIL @ ATL", "time_et": "1:35 PM ET", "away": "MIL", "home": "ATL",
        "away_sp": "Robert Gasser", "home_sp": "Bryce Elder",
        "market_total": 8.0, "market_ml_home": -145, "market_ml_away": 122,
        "weather": "Outdoor, 86°F", "wind": "9 mph out",
    },
    {
        "game": "WSH @ TB", "time_et": "1:40 PM ET", "away": "WSH", "home": "TB",
        "away_sp": "Andrew Alvarez", "home_sp": "Nick Martinez",
        "market_total": 7.5, "market_ml_home": -162, "market_ml_away": 137,
        "weather": "Dome", "wind": "N/A",
    },
    {
        "game": "CWS @ DET", "time_et": "1:40 PM ET", "away": "CWS", "home": "DET",
        "away_sp": "Davis Martin", "home_sp": "Keider Montero",
        "market_total": 8.0, "market_ml_home": -175, "market_ml_away": 148,
        "weather": "Outdoor, 79°F", "wind": "10 mph out",
    },
    {
        "game": "SF @ MIA", "time_et": "1:40 PM ET", "away": "SF", "home": "MIA",
        "away_sp": "Logan Webb", "home_sp": "Ryan Gusto",
        "market_total": 7.0, "market_ml_home": 130, "market_ml_away": -155,
        "weather": "Dome (retractable)", "wind": "N/A",
    },
    {
        "game": "CLE @ HOU", "time_et": "2:10 PM ET", "away": "CLE", "home": "HOU",
        "away_sp": "Slade Cecconi", "home_sp": "Kai-Wei Teng",
        "market_total": 8.5, "market_ml_home": -145, "market_ml_away": 122,
        "weather": "Dome (retractable)", "wind": "N/A",
    },
    {
        "game": "STL @ KC", "time_et": "2:10 PM ET", "away": "STL", "home": "KC",
        "away_sp": "Dustin May", "home_sp": "Stephen Kolek",
        "market_total": 8.0, "market_ml_home": -128, "market_ml_away": 108,
        "weather": "Outdoor, 83°F", "wind": "12 mph out",
    },
    {
        "game": "TOR @ CHC", "time_et": "2:20 PM ET", "away": "TOR", "home": "CHC",
        "away_sp": "Dylan Cease", "home_sp": "Shota Imanaga",
        "market_total": 7.0, "market_ml_home": -135, "market_ml_away": 114,
        "weather": "Outdoor, 81°F", "wind": "8 mph in",
    },
    {
        "game": "SD @ TEX", "time_et": "2:35 PM ET", "away": "SD", "home": "TEX",
        "away_sp": "Wandy Peralta", "home_sp": "Nathan Eovaldi",
        "market_total": 8.5, "market_ml_home": -148, "market_ml_away": 125,
        "weather": "Dome (AC)", "wind": "N/A",
    },
    {
        "game": "PIT @ COL", "time_et": "3:10 PM ET", "away": "PIT", "home": "COL",
        "away_sp": "Jared Jones", "home_sp": "Michael Lorenzen",
        "market_total": 12.0, "market_ml_home": -108, "market_ml_away": -108,
        "weather": "Outdoor, 92°F", "wind": "7 mph out",
    },
    {
        "game": "MIN @ ARI", "time_et": "3:15 PM ET", "away": "MIN", "home": "ARI",
        "away_sp": "Mike Paredes", "home_sp": "Jose Cabrera",
        "market_total": 9.0, "market_ml_home": -148, "market_ml_away": 125,
        "weather": "Dome (AC)", "wind": "N/A",
    },
    {
        "game": "LAA @ OAK", "time_et": "4:05 PM ET", "away": "LAA", "home": "OAK",
        "away_sp": "Reid Detmers", "home_sp": "Jack Perkins",
        "market_total": 8.5, "market_ml_home": -125, "market_ml_away": 105,
        "weather": "Outdoor, 88°F", "wind": "6 mph in",
    },
    {
        "game": "BAL @ LAD", "time_et": "4:10 PM ET", "away": "BAL", "home": "LAD",
        "away_sp": "Brandon Young", "home_sp": "Emmet Sheehan",
        "market_total": 7.5, "market_ml_home": -195, "market_ml_away": 165,
        "weather": "Outdoor, 84°F", "wind": "9 mph out",
    },
    {
        "game": "BOS @ SEA", "time_et": "4:10 PM ET", "away": "BOS", "home": "SEA",
        "away_sp": "Payton Tolle", "home_sp": "Logan Gilbert",
        "market_total": 7.0, "market_ml_home": -185, "market_ml_away": 158,
        "weather": "Outdoor, 75°F", "wind": "11 mph in",
    },
    {
        "game": "NYM @ PHI", "time_et": "7:20 PM ET", "away": "NYM", "home": "PHI",
        "away_sp": "David Peterson", "home_sp": "Zack Wheeler",
        "market_total": 7.5, "market_ml_home": -195, "market_ml_away": 165,
        "weather": "Outdoor, 89°F", "wind": "10 mph out",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def proj_runs(t_off: dict, t_def: dict, sp_era: float, park: float, custom_adj: float = 0.0) -> float:
    """Project runs scored by one team against a specific SP."""
    base = (t_off["rpg"] + sp_era) / 2
    net = (t_off["rpg"] - t_def["ra_g"]) * 0.08
    total = (base + net + custom_adj) * park
    return round(max(total, 1.5), 2)


def win_prob(proj_home: float, proj_away: float) -> tuple[float, float]:
    """Pythagorean win probability."""
    exp = 1.83
    h = proj_home ** exp
    a = proj_away ** exp
    hp = h / (h + a)
    return round(hp, 4), round(1 - hp, 4)


def ml_implied(american_odds: int) -> float:
    """Convert American odds to implied probability."""
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    else:
        return 100 / (american_odds + 100)


def edge_pct(model_prob: float, market_prob: float) -> float:
    return round((model_prob - market_prob) * 100, 1)


def recommend(conf: float) -> str:
    if conf >= 65:
        return "✅ STRONG BET"
    elif conf >= 55:
        return "⚠️ MEDIUM"
    else:
        return "❌ PASS"


def nrfi_prob(sp_away: dict, sp_home: dict) -> float:
    """Probability no run scores in the first inning."""
    nrfi = sp_away["nrfi_rate"] * sp_home["nrfi_rate"]
    return round(min(nrfi, 0.95), 3)


def pitcher_props(sp_name: str, sp: dict, opp_team: str) -> List[dict]:
    """Generate 4 pitcher prop recommendations."""
    opp = TEAM[opp_team]
    
    # Strikeout line: based on K/9 × projected IP
    k_proj = round(sp["k9"] * sp["ip"] / 9.0, 1)
    k_line = round(math.floor(k_proj * 2) / 2, 1)  # round to nearest 0.5 below
    k_prob = 0.55 + (k_proj - k_line) * 0.12
    k_prob = min(k_prob, 0.82)
    
    # Walk line
    bb_proj = round(sp["bb9"] * sp["ip"] / 9.0, 1)
    bb_line = round(math.ceil(bb_proj * 2) / 2, 1)
    bb_under_prob = 0.52 + (bb_line - bb_proj) * 0.10
    bb_under_prob = min(bb_under_prob, 0.78)
    
    # ERA / Runs allowed line
    runs_proj = round(sp["era"] * sp["ip"] / 9.0, 1)
    runs_line = round(math.ceil(runs_proj * 2) / 2, 1)
    runs_under_prob = 0.53 + (runs_line - runs_proj) * 0.09
    runs_under_prob = min(runs_under_prob, 0.78)
    
    # IP over
    ip_line = round(sp["ip"] - 0.5, 1)
    ip_over_prob = 0.60 if sp["era"] < 4.0 else 0.53
    
    return [
        {"stat": "Strikeouts", "choice": "Over", "line": k_line, "proj": k_proj,
         "prob": round(k_prob, 2), "rec": recommend(k_prob * 100)},
        {"stat": "Walks",      "choice": "Under", "line": bb_line, "proj": bb_proj,
         "prob": round(bb_under_prob, 2), "rec": recommend(bb_under_prob * 100)},
        {"stat": "Runs Allowed","choice": "Under", "line": runs_line, "proj": runs_proj,
         "prob": round(runs_under_prob, 2), "rec": recommend(runs_under_prob * 100)},
        {"stat": "Innings Pitched","choice": "Over", "line": ip_line, "proj": sp["ip"],
         "prob": round(ip_over_prob, 2), "rec": recommend(ip_over_prob * 100)},
    ]


def hitter_props(team: str, opp_sp: dict) -> List[dict]:
    """Generate hitter prop recommendations for top 4 players."""
    props = []
    for h in HITTERS.get(team, []):
        # Adjust hits for opposing SP ERA
        era_adj = (4.30 - opp_sp["era"]) * 0.03  # better pitcher = fewer hits
        h_prob = 0.60 + (h["hits_avg"] - 1.0) * 0.12 - era_adj
        h_prob = round(min(max(h_prob, 0.42), 0.82), 2)
        
        rbi_line = 0.5
        rbi_prob = round(min(0.48 + h["rbi_avg"] * 0.18, 0.78), 2)
        
        hr_prob = round(min(h["hr_rate"] * 4.5, 0.45), 2)
        hr_rec = recommend(hr_prob * 100)
        
        props.append({
            "name": h["name"], "pos": h["pos"],
            "hit_over": "+0.5",  "hit_prob": h_prob, "hit_rec": recommend(h_prob * 100),
            "rbi_over": "+0.5",  "rbi_prob": rbi_prob, "rbi_rec": recommend(rbi_prob * 100),
            "hr_line": "+0.5",   "hr_prob": hr_prob, "hr_rec": hr_rec,
        })
    return props


def analyze_game(g: dict) -> dict:
    """Full analysis for one game."""
    away_t = TEAM[g["away"]]
    home_t = TEAM[g["home"]]
    park_r = PARK[g["home"]]["run"]
    
    away_sp_key = g["away_sp"]
    home_sp_key = g["home_sp"]
    
    # Fallback for name mismatches
    away_sp = PITCHERS.get(away_sp_key, PITCHERS.get("Davis Martin"))
    home_sp = PITCHERS.get(home_sp_key, PITCHERS.get("Davis Martin"))
    
    away_proj = proj_runs(away_t, home_t, home_sp["era"], park_r)
    home_proj = proj_runs(home_t, away_t, away_sp["era"], park_r)
    total_proj = round(away_proj + home_proj, 2)
    
    # Totals analysis
    ou_edge = round(total_proj - g["market_total"], 2)
    ou_direction = "OVER" if ou_edge > 0 else "UNDER"
    ou_conf = min(abs(ou_edge) * 22, 78.0)
    
    # Moneyline
    hp, ap = win_prob(home_proj, away_proj)
    mkt_hp = ml_implied(g["market_ml_home"])
    mkt_ap = ml_implied(g["market_ml_away"])
    home_ml_edge = edge_pct(hp, mkt_hp)
    away_ml_edge = edge_pct(ap, mkt_ap)
    
    if home_ml_edge >= away_ml_edge:
        ml_pick = home_t["name"]
        ml_odds = g["market_ml_home"]
        ml_prob = hp
        ml_edge = home_ml_edge
    else:
        ml_pick = away_t["name"]
        ml_odds = g["market_ml_away"]
        ml_prob = ap
        ml_edge = away_ml_edge
    
    ml_conf = min(50 + abs(ml_edge) * 4.5, 80.0)
    
    # Run line (-1.5 fav / +1.5 dog)
    margin = abs(home_proj - away_proj)
    rl_fav = home_t["name"] if home_proj > away_proj else away_t["name"]
    rl_fav_abbr = g["home"] if home_proj > away_proj else g["away"]
    rl_fav_ml = g["market_ml_home"] if home_proj > away_proj else g["market_ml_away"]
    
    # Win by 2+ probability approximation
    rl_conf = min(40 + margin * 15, 75.0)
    
    # NRFI/YRFI
    nrfi = nrfi_prob(away_sp, home_sp)
    yrfi = round(1 - nrfi, 3)
    nrfi_conf = nrfi * 100
    yrfi_conf = yrfi * 100
    nrfi_pick = "NRFI" if nrfi >= 0.55 else "YRFI"
    nrfi_val = nrfi if nrfi >= 0.55 else yrfi
    nrfi_conf_val = nrfi_val * 100
    
    # Pitcher props
    away_pitcher_props = pitcher_props(away_sp_key, away_sp, g["home"])
    home_pitcher_props = pitcher_props(home_sp_key, home_sp, g["away"])
    
    # Hitter props
    away_hitter_props = hitter_props(g["away"], home_sp)
    home_hitter_props = hitter_props(g["home"], away_sp)
    
    # Determine bests per market
    best_ou_conf = round(ou_conf, 1)
    best_ml_conf = round(ml_conf, 1)
    best_rl_conf = round(rl_conf, 1)
    best_nrfi_conf = round(nrfi_conf_val, 1)
    
    # Overall game tier
    max_conf = max(best_ou_conf, best_ml_conf, best_rl_conf, best_nrfi_conf)
    tier = recommend(max_conf)
    
    # Collect strong bets
    strong_bets = []
    
    if best_ou_conf >= 65:
        strong_bets.append({
            "market": "Total",
            "pick": f"{ou_direction} {g['market_total']}",
            "conf": best_ou_conf,
            "edge": f"{ou_edge:+.2f} runs",
            "proj": f"{total_proj}",
        })
    if best_ml_conf >= 65:
        odds_str = f"+{ml_odds}" if ml_odds > 0 else str(ml_odds)
        strong_bets.append({
            "market": "Moneyline",
            "pick": f"{ml_pick} {odds_str}",
            "conf": best_ml_conf,
            "edge": f"{ml_edge:+.1f}%",
            "proj": f"Win Prob {ml_prob*100:.1f}%",
        })
    if best_rl_conf >= 65:
        strong_bets.append({
            "market": "Run Line",
            "pick": f"{rl_fav} -1.5",
            "conf": best_rl_conf,
            "edge": f"+{margin:.2f} runs margin",
            "proj": f"Margin {margin:.2f}",
        })
    if best_nrfi_conf >= 65:
        strong_bets.append({
            "market": "NRFI/YRFI",
            "pick": nrfi_pick,
            "conf": best_nrfi_conf,
            "edge": f"{nrfi_val*100:.1f}% probability",
            "proj": f"NRFI:{nrfi*100:.1f}% YRFI:{yrfi*100:.1f}%",
        })
    
    # Collect strong player props
    strong_player_props = []
    for pp in away_pitcher_props + home_pitcher_props:
        if pp["prob"] >= 0.65:
            strong_player_props.append(pp)
    for hp_item in away_hitter_props + home_hitter_props:
        if hp_item["hit_prob"] >= 0.65:
            strong_player_props.append({
                "stat": f"{hp_item['name']} Hit Over {hp_item['hit_over']}",
                "prob": hp_item["hit_prob"],
                "rec": hp_item["hit_rec"],
            })
        if hp_item["rbi_prob"] >= 0.65:
            strong_player_props.append({
                "stat": f"{hp_item['name']} RBI Over {hp_item['rbi_over']}",
                "prob": hp_item["rbi_prob"],
                "rec": hp_item["rbi_rec"],
            })
    
    return {
        "game": g["game"], "time_et": g["time_et"],
        "away": g["away"], "home": g["home"],
        "away_team": away_t["name"], "home_team": home_t["name"],
        "away_sp": away_sp_key, "home_sp": home_sp_key,
        "venue": PARK[g["home"]]["name"],
        "away_proj": away_proj, "home_proj": home_proj, "total_proj": total_proj,
        "market_total": g["market_total"],
        "ou_direction": ou_direction, "ou_edge": ou_edge, "ou_conf": best_ou_conf,
        "ml_pick": ml_pick, "ml_odds": ml_odds, "ml_prob": ml_prob,
        "ml_edge": ml_edge, "ml_conf": best_ml_conf,
        "rl_fav": rl_fav, "rl_margin": margin, "rl_conf": best_rl_conf,
        "nrfi_pick": nrfi_pick, "nrfi_val": round(nrfi_val*100,1),
        "nrfi_conf": best_nrfi_conf, "nrfi_pct": round(nrfi*100,1), "yrfi_pct": round(yrfi*100,1),
        "hp": hp, "ap": ap, "home_win_pct": round(hp*100,1), "away_win_pct": round(ap*100,1),
        "tier": tier, "max_conf": max_conf,
        "away_pitcher_props": away_pitcher_props,
        "home_pitcher_props": home_pitcher_props,
        "away_hitter_props": away_hitter_props,
        "home_hitter_props": home_hitter_props,
        "strong_bets": strong_bets,
        "strong_player_props": strong_player_props,
        "weather": g["weather"], "wind": g["wind"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# DISCORD PUSH
# ─────────────────────────────────────────────────────────────────────────────

def send_discord(payload: dict) -> bool:
    if not DISCORD_WEBHOOK:
        log.warning("DISCORD_WEBHOOK_URL not set — skipping Discord push")
        return False
    if requests is None:
        log.error("requests library not available")
        return False
    try:
        resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Discord push failed: {e}")
        return False


def push_strong_bet_to_discord(result: dict) -> None:
    """Push only strong bets for this game to Discord."""
    if not result["strong_bets"]:
        log.info(f"[Discord] No strong bets for {result['game']} — logged only")
        return
    
    # Color: green for strong
    color = 3066993  # green
    
    # Header embed
    fields = []
    
    # Game info
    fields.append({
        "name": "⚾ Matchup",
        "value": f"**{result['away_team']}** @ **{result['home_team']}**",
        "inline": True
    })
    fields.append({
        "name": "🕐 Time",
        "value": result["time_et"],
        "inline": True
    })
    fields.append({
        "name": "🏟️ Venue",
        "value": result["venue"],
        "inline": True
    })
    fields.append({
        "name": "📊 Projected Score",
        "value": f"{result['away_team']}: **{result['away_proj']}** | {result['home_team']}: **{result['home_proj']}** | Total: **{result['total_proj']}**",
        "inline": False
    })
    fields.append({
        "name": "⚾ Starting Pitchers",
        "value": f"{result['away_sp']} vs {result['home_sp']}",
        "inline": False
    })
    
    # Win probabilities
    fields.append({
        "name": "📈 Win Probabilities",
        "value": f"{result['away_team']}: **{result['away_win_pct']}%** | {result['home_team']}: **{result['home_win_pct']}%**",
        "inline": False
    })
    
    # Strong bets section
    strong_lines = ""
    for sb in result["strong_bets"]:
        strong_lines += f"🔥 **{sb['market']}**: {sb['pick']} | Conf: {sb['conf']:.0f}% | Edge: {sb['edge']}\n"
    
    fields.append({
        "name": "💰 STRONG BETS",
        "value": strong_lines or "None",
        "inline": False
    })
    
    # NRFI/YRFI
    fields.append({
        "name": "1️⃣ NRFI/YRFI",
        "value": f"NRFI: **{result['nrfi_pct']}%** | YRFI: **{result['yrfi_pct']}%** → **{result['nrfi_pick']}** ({result['nrfi_conf']:.0f}% conf)",
        "inline": False
    })
    
    # Top strong player props
    if result["strong_player_props"]:
        pp_lines = ""
        for pp in result["strong_player_props"][:5]:
            stat = pp.get("stat", "")
            prob = pp.get("prob", 0)
            pp_lines += f"• {stat} — {prob*100:.0f}%\n"
        fields.append({
            "name": "🎯 Strong Player Props",
            "value": pp_lines,
            "inline": False
        })
    
    embed = {
        "title": f"⚾ MLB STRONG BET | {result['game']} | {result['time_et']}",
        "description": f"🔥 **{len(result['strong_bets'])} Strong Bet(s) Identified** | Max Confidence: **{result['max_conf']:.0f}%**",
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {"text": f"MultiSportPredict | MLB | {DATE_LABEL}"}
    }
    
    payload = {"embeds": [embed]}
    ok = send_discord(payload)
    if ok:
        log.info(f"[Discord ✓] Pushed strong bets for {result['game']}")
        print(f"  📤 Discord: Pushed strong bets for {result['game']}")
    else:
        log.warning(f"[Discord ✗] Failed to push {result['game']}")


def push_daily_summary_to_discord(results: List[dict]) -> None:
    """Push end-of-day summary with all strong bets."""
    strong_games = [r for r in results if r["strong_bets"]]
    if not strong_games:
        log.info("[Discord] No strong bets today — no summary pushed")
        return
    
    fields = []
    fields.append({
        "name": f"📅 Date",
        "value": DATE_LABEL,
        "inline": True
    })
    fields.append({
        "name": "⚾ Total Games",
        "value": str(len(results)),
        "inline": True
    })
    fields.append({
        "name": "🔥 Games w/ Strong Bets",
        "value": str(len(strong_games)),
        "inline": True
    })
    
    summary_lines = ""
    for r in strong_games:
        for sb in r["strong_bets"]:
            summary_lines += f"• {r['game']} ({r['time_et']}) — **{sb['market']}**: {sb['pick']} [{sb['conf']:.0f}%]\n"
    
    fields.append({
        "name": "💰 All Strong Bets Today",
        "value": summary_lines[:1000] if summary_lines else "None",
        "inline": False
    })
    
    embed = {
        "title": f"⚾ MLB DAILY STRONG BETS SUMMARY | {DATE_LABEL}",
        "description": f"Top value plays across the **{len(results)}-game Sunday slate** — strong bets only",
        "color": 3066993,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {"text": "MultiSportPredict | Daily Summary"}
    }
    
    ok = send_discord({"embeds": [embed]})
    if ok:
        print(f"\n  📤 Discord: Pushed daily summary ({len(strong_games)} strong-bet games)")
    else:
        log.warning("[Discord] Failed to push daily summary")


# ─────────────────────────────────────────────────────────────────────────────
# RICH TERMINAL OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

SEP  = "=" * 120
SEP2 = "-" * 120
SEP3 = "─" * 120

def tier_label(conf: float) -> str:
    if conf >= 65: return "★★★★★ STRONG BET"
    if conf >= 55: return "★★★★  MEDIUM    "
    if conf >= 45: return "★★★   LEAN      "
    return              "★★    PASS      "


def print_header():
    print(SEP)
    print(f"  ⚾  MLB FULL SLATE — {DATE_LABEL.upper()}  ⚾")
    print(f"  15 GAMES | Moneyline · Run Line · Totals · NRFI/YRFI · Pitcher Props · Hitter Props")
    print(f"  Generated: {datetime.now().strftime('%I:%M:%S %p ET')}")
    print(SEP)


def print_game_analysis(r: dict, idx: int):
    print(f"\n{'#'*3} GAME {idx:02d} | {r['game']:12s} | {r['time_et']:12s} | {r['venue']}")
    print(SEP2)
    
    # Projected score + pitchers
    print(f"  ⚾  {r['away_team']:25s} {r['away_proj']:5.2f} — {r['home_proj']:5.2f}  {r['home_team']}")
    print(f"  📍  Proj Total: {r['total_proj']:<5.2f} | Market: {r['market_total']:<5} | Weather: {r['weather']} | Wind: {r['wind']}")
    print(f"  🗣️   SP: {r['away_sp']:30s} vs  {r['home_sp']}")
    print(f"  📈  Win%: {r['away_team']} {r['away_win_pct']:.1f}%  |  {r['home_team']} {r['home_win_pct']:.1f}%")
    print()
    
    # Markets table
    print(f"  {'MARKET':15s}  {'PICK':40s}  {'CONF':7s}  {'EDGE':12s}  {'TIER'}")
    print(f"  {'-'*15}  {'-'*40}  {'-'*7}  {'-'*12}  {'-'*18}")
    
    # Totals
    ou_str = f"{r['ou_direction']} {r['market_total']} (Proj: {r['total_proj']})"
    print(f"  {'Total':15s}  {ou_str:40s}  {r['ou_conf']:5.1f}%   {r['ou_edge']:+.2f} runs   {tier_label(r['ou_conf'])}")
    
    # Moneyline
    ml_odds_str = f"+{r['ml_odds']}" if r['ml_odds'] > 0 else str(r['ml_odds'])
    ml_str = f"{r['ml_pick']} ({ml_odds_str}) Prob:{r['ml_prob']*100:.1f}%"
    print(f"  {'Moneyline':15s}  {ml_str:40s}  {r['ml_conf']:5.1f}%   {r['ml_edge']:+.1f}%        {tier_label(r['ml_conf'])}")
    
    # Run Line
    rl_str = f"{r['rl_fav']} -1.5 (Margin: {r['rl_margin']:.2f}r)"
    print(f"  {'Run Line':15s}  {rl_str:40s}  {r['rl_conf']:5.1f}%   {r['rl_margin']:+.2f} runs   {tier_label(r['rl_conf'])}")
    
    # NRFI/YRFI
    nrfi_str = f"{r['nrfi_pick']} (NRFI:{r['nrfi_pct']}% YRFI:{r['yrfi_pct']}%)"
    print(f"  {'NRFI/YRFI':15s}  {nrfi_str:40s}  {r['nrfi_conf']:5.1f}%   —            {tier_label(r['nrfi_conf'])}")
    
    print()
    
    # Pitcher Props
    print(f"  ── PITCHER PROPS ──────────────────────────────────────────────────────────────────────")
    for side, sp_name, props in [
        (r["away_team"], r["away_sp"], r["away_pitcher_props"]),
        (r["home_team"], r["home_sp"], r["home_pitcher_props"]),
    ]:
        print(f"  🔵 {sp_name} ({side})")
        for pp in props:
            arrow = "▲" if pp["choice"] == "Over" else "▼"
            print(f"     {arrow} {pp['stat']:18s}  {pp['choice']:5s} {pp['line']:<5}  Proj:{pp['proj']:<5}  {pp['prob']*100:4.0f}%  {pp['rec']}")
    
    print()
    
    # Hitter Props
    print(f"  ── HITTER PROPS ───────────────────────────────────────────────────────────────────────")
    for side, team_abbr, props in [
        (r["away_team"], r["away"], r["away_hitter_props"]),
        (r["home_team"], r["home"], r["home_hitter_props"]),
    ]:
        print(f"  🟠 {side}")
        print(f"     {'PLAYER':22s}  {'POS':4s}  {'HITS>+0.5':10s}  {'RBI>+0.5':10s}  {'HR>+0.5':8s}")
        print(f"     {'-'*22}  {'-'*4}  {'-'*10}  {'-'*10}  {'-'*8}")
        for h in props:
            hr_pct = f"{h['hr_prob']*100:.0f}%"
            print(f"     {h['name']:22s}  {h['pos']:4s}  {h['hit_prob']*100:4.0f}% {h['hit_rec']:15s}  {h['rbi_prob']*100:4.0f}% {h['rbi_rec']:15s}  {hr_pct:6s} {h['hr_rec']}")
    
    print()
    
    # Strong bets callout
    if r["strong_bets"]:
        print(f"  🔥🔥 STRONG BETS FOR THIS GAME → PUSHED TO DISCORD:")
        for sb in r["strong_bets"]:
            print(f"     ✅ {sb['market']:12s}  {sb['pick']:35s}  Conf: {sb['conf']:.0f}%  Edge: {sb['edge']}")
    else:
        print(f"  ℹ️  No strong bets — all markets logged only (not pushed to Discord)")
    
    print(SEP3)


def print_slate_summary(results: List[dict]):
    strong = [r for r in results if r["strong_bets"]]
    print(f"\n{SEP}")
    print(f"  📋 SLATE SUMMARY — {DATE_LABEL} — {len(results)} GAMES")
    print(SEP)
    
    print(f"\n  {'GAME':14s}  {'TIME':12s}  {'TOTAL':12s}  {'ML PICK':30s}  {'NRFI':8s}  {'MAX CONF':9s}  TIER")
    print(f"  {'-'*14}  {'-'*12}  {'-'*12}  {'-'*30}  {'-'*8}  {'-'*9}  {'-'*20}")
    
    for r in sorted(results, key=lambda x: x["max_conf"], reverse=True):
        ml_o = f"+{r['ml_odds']}" if r['ml_odds'] > 0 else str(r['ml_odds'])
        total_str = f"{r['ou_direction']} {r['market_total']}"
        ml_str = f"{r['ml_pick']} ({ml_o})"
        print(f"  {r['game']:14s}  {r['time_et']:12s}  {total_str:12s}  {ml_str:30s}  {r['nrfi_pick']:8s}  {r['max_conf']:6.1f}%    {tier_label(r['max_conf'])}")
    
    print(f"\n{SEP}")
    print(f"  🔥 TOP STRONG BETS ({len(strong)} games)")
    print(SEP)
    
    all_strong = []
    for r in results:
        for sb in r["strong_bets"]:
            all_strong.append((r, sb))
    
    all_strong.sort(key=lambda x: x[1]["conf"], reverse=True)
    
    for r, sb in all_strong:
        ml_o = f"+{r['ml_odds']}" if r['ml_odds'] > 0 else str(r['ml_odds'])
        print(f"  ✅ {r['game']:12s} | {r['time_et']:12s} | {sb['market']:12s}: {sb['pick']:35s} | Conf: {sb['conf']:.0f}% | Edge: {sb['edge']}")
    
    if not all_strong:
        print("  ℹ️  No strong bets identified across today's slate.")
    
    # NRFI summary
    print(f"\n{SEP}")
    print(f"  1️⃣  NRFI/YRFI SUMMARY")
    print(SEP)
    nrfi_list = sorted(results, key=lambda x: x["nrfi_conf"] if x["nrfi_pick"] == "NRFI" else x["yrfi_pct"], reverse=True)
    for r in nrfi_list:
        tier = tier_label(r["nrfi_conf"])
        print(f"  {r['game']:14s}  {r['time_et']:12s}  {r['nrfi_pick']:5s}  NRFI:{r['nrfi_pct']:5.1f}%  YRFI:{r['yrfi_pct']:5.1f}%  Conf:{r['nrfi_conf']:5.1f}%  {tier}")
    
    print(f"\n{SEP}")
    print(f"  ℹ️  DISCORD: {len(strong)} game(s) had strong bets pushed | {len(results)-len(strong)} game(s) logged only")
    print(SEP)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    log.info(f"=== MLB FULL SLATE ANALYSIS START | {DATE_LABEL} ===")
    print_header()
    
    results = []
    for idx, g in enumerate(SLATE, 1):
        r = analyze_game(g)
        results.append(r)
        print_game_analysis(r, idx)
        log.info(
            f"[ANALYZED] {r['game']} | Proj: {r['away_proj']}-{r['home_proj']} "
            f"| Total: {r['total_proj']} ({r['ou_direction']} {r['market_total']}) "
            f"| ML: {r['ml_pick']} ({r['ml_conf']:.0f}%) "
            f"| {r['nrfi_pick']} ({r['nrfi_conf']:.0f}%) "
            f"| StrongBets: {len(r['strong_bets'])}"
        )
    
    # Push strong bets to Discord per game
    print(f"\n{'='*60}")
    print("  📤 DISCORD PUSH — STRONG BETS ONLY")
    print(f"{'='*60}")
    for r in results:
        if r["strong_bets"]:
            push_strong_bet_to_discord(r)
        else:
            log.info(f"[LOG ONLY] {r['game']} — no strong bets, not pushed to Discord")
    
    # Push daily summary
    push_daily_summary_to_discord(results)
    
    # Print summary
    print_slate_summary(results)
    
    # Save JSON log
    log_path = f"mlb_june21_2026_results.json"
    with open(log_path, "w") as f:
        json.dump([{k: v for k, v in r.items() 
                    if k not in ("away_hitter_props","home_hitter_props",
                                 "away_pitcher_props","home_pitcher_props")} 
                   for r in results], f, indent=2)
    print(f"\n  💾 Full results saved to: {log_path}")
    log.info(f"=== MLB FULL SLATE ANALYSIS COMPLETE | {len(results)} games | {DATE_LABEL} ===")


if __name__ == "__main__":
    main()
