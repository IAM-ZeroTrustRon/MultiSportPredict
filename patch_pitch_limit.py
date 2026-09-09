#!/usr/bin/env python3
"""Add starting-pitcher pitch limits to the baseball model.

Threads `pitch_limit` through the existing sp_overrides plumbing so a capped
start (Burnes at 60 pitches in his first game back) shortens the innings the
starter is credited with, hands the rest to the bullpen, and moves the runs
and strikeout projections accordingly.

Every edit is anchored on an exact unique string and refuses if the anchor is
missing or ambiguous. CRLF endings are preserved.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")


def load(name):
    raw = (ROOT / name).read_bytes()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8").replace("\r\n", "\n"), crlf


def save(name, text, crlf):
    out = text.replace("\n", "\r\n") if crlf else text
    (ROOT / name).write_bytes(out.encode("utf-8"))


def sub(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ABORT [{label}]: anchor found {count} times, expected 1")
    return text.replace(old, new)


# ===========================================================================
# predict_match.py
# ===========================================================================
pm, pm_crlf = load("predict_match.py")

if "pitch_limit" in pm:
    raise SystemExit("ABORT: predict_match.py already patched")

# --- A. workload block, inserted just before the SP override application ----
OLD_A = """    # 1b) Apply live starting-pitcher overrides, if supplied, so today's
    # actual starter (not the league-average baseline) drives the projection.
    if home_sp_overrides:"""

NEW_A = '''    # 1a) Starter workload.
    #
    # The override block below overwrites team ERA and K/9 with the starter's
    # own numbers, and everything downstream then treated those as if the
    # starter threw all nine innings. He does not. A league-average start is
    # 5.4 innings; the other 3.5 belong to relievers this project has no
    # separate read on, so the team staff rate -- captured here, before the
    # overwrite -- stands in for them. It is a real team number, not a
    # constant, and it is labelled as a proxy in the stored result.
    #
    # A pitch limit is the only thing that shortens the first term. Pass
    # pitch_limit in the sp_overrides dict for a starter on a cap (rehab
    # start, opener, innings-managed rookie). Without one, the split is the
    # league average and the arithmetic below is unchanged.
    _PITCHES_PER_INNING = 16.5   # MLB starter average, 2025-26
    _GAME_INNINGS = 8.9          # a nine-inning game averages just under 9
    _BASELINE_SP_INNINGS = 5.4   # league-average start length, uncapped

    _pen = {
        "home_era": float(home_stats.get("era") or 4.20),
        "away_era": float(away_stats.get("era") or 4.20),
        "home_k9": float(home_stats.get("k_projection_per_9") or 8.0),
        "away_k9": float(away_stats.get("k_projection_per_9") or 8.0),
    }

    def _starter_innings(overrides: Optional[Dict[str, float]]) -> float:
        """Innings the starter is expected to cover."""
        limit = (overrides or {}).get("pitch_limit")
        if limit is None:
            return _BASELINE_SP_INNINGS
        return max(0.0, min(7.0, float(limit) / _PITCHES_PER_INNING))

    def _blended_era(sp_era: float, pen_era: float,
                     sp_ip: float, pen_ip: float) -> float:
        """Innings-weighted ERA across the starter and the relief innings."""
        innings = sp_ip + pen_ip
        if innings <= 0:
            return pen_era
        return (sp_era * sp_ip + pen_era * pen_ip) / innings

    home_sp_ip = _starter_innings(home_sp_overrides)
    away_sp_ip = _starter_innings(away_sp_overrides)
    home_pen_ip = max(0.0, _GAME_INNINGS - home_sp_ip)
    away_pen_ip = max(0.0, _GAME_INNINGS - away_sp_ip)
    home_capped = (home_sp_overrides or {}).get("pitch_limit") is not None
    away_capped = (away_sp_overrides or {}).get("pitch_limit") is not None

    for _side, _capped, _limit, _ip, _pen_ip in (
        ("Home", home_capped, (home_sp_overrides or {}).get("pitch_limit"),
         home_sp_ip, home_pen_ip),
        ("Away", away_capped, (away_sp_overrides or {}).get("pitch_limit"),
         away_sp_ip, away_pen_ip),
    ):
        if _capped:
            print(f"    {_side} SP pitch limit {int(_limit)} -> "
                  f"{_ip:.1f} IP starter / {_pen_ip:.1f} IP bullpen "
                  f"(league-average start is {_BASELINE_SP_INNINGS} IP)")

    # 1b) Apply live starting-pitcher overrides, if supplied, so today's
    # actual starter (not the league-average baseline) drives the projection.
    if home_sp_overrides:'''

pm = sub(pm, OLD_A, NEW_A, "A: workload block")

# --- B. runs projection now innings-weighted ------------------------------
OLD_B = """    proj_home = home_stats["runs_per_game"] + (away_stats["era"] - 4.0) * 0.3
    proj_away = away_stats["runs_per_game"] + (home_stats["era"] - 4.0) * 0.3
    total_proj = proj_home + proj_away"""

NEW_B = '''    # Runs allowed follow whoever is on the mound, weighted by innings. This
    # line used to apply the starter's ERA to the whole game, which credited
    # (or blamed) him for three and a half innings he never pitched. With no
    # override and no cap, both terms are the same team ERA and this is
    # identical to what it replaced.
    home_eff_era = _blended_era(float(home_stats["era"]), _pen["home_era"],
                                home_sp_ip, home_pen_ip)
    away_eff_era = _blended_era(float(away_stats["era"]), _pen["away_era"],
                                away_sp_ip, away_pen_ip)

    proj_home = home_stats["runs_per_game"] + (away_eff_era - 4.0) * 0.3
    proj_away = away_stats["runs_per_game"] + (home_eff_era - 4.0) * 0.3
    total_proj = proj_home + proj_away'''

pm = sub(pm, OLD_B, NEW_B, "B: runs projection")

# --- C. record the workload in the result (and therefore in raw_json) -----
OLD_C = """        "props": {},
        "summary": {},
        "data_source": home_stats.get("source", "baseline"),
    }"""

NEW_C = '''        "props": {},
        "summary": {},
        "data_source": home_stats.get("source", "baseline"),
        # Stored so grading can separate capped starts from normal ones later.
        "starter_workload": {
            "home_pitch_limit": (home_sp_overrides or {}).get("pitch_limit"),
            "away_pitch_limit": (away_sp_overrides or {}).get("pitch_limit"),
            "home_starter_innings": round(home_sp_ip, 2),
            "away_starter_innings": round(away_sp_ip, 2),
            "home_bullpen_innings": round(home_pen_ip, 2),
            "away_bullpen_innings": round(away_pen_ip, 2),
            "pitches_per_inning": _PITCHES_PER_INNING,
            "relief_rate_source": (
                "team staff ERA/K9 -- relief-only splits are not ingested"),
        },
    }'''

pm = sub(pm, OLD_C, NEW_C, "C: starter_workload in result")

# --- D. strikeouts split between starter and bullpen ----------------------
OLD_D = """            _INNINGS = 8.9          # a nine-inning game averages just under 9
            home_k_proj = float(home_stats.get("k_projection_per_9", 8.0)) * _INNINGS / 9.0
            away_k_proj = float(away_stats.get("k_projection_per_9", 8.0)) * _INNINGS / 9.0"""

NEW_D = '''            # Split the same way: the starter's K/9 for the innings he
            # covers, the staff rate for the rest. A pitch limit shortens the
            # first term and lengthens the second, which is why a capped
            # strikeout artist projects fewer team strikeouts, not more.
            home_sp_k9 = float((home_sp_overrides or {}).get("k9")
                               or _pen["home_k9"])
            away_sp_k9 = float((away_sp_overrides or {}).get("k9")
                               or _pen["away_k9"])
            home_k_proj = (home_sp_k9 * home_sp_ip
                           + _pen["home_k9"] * home_pen_ip) / 9.0
            away_k_proj = (away_sp_k9 * away_sp_ip
                           + _pen["away_k9"] * away_pen_ip) / 9.0'''

pm = sub(pm, OLD_D, NEW_D, "D: strikeout split")

# --- E. flag the strikeout prop when a cap is in play ---------------------
OLD_E = '''                "home_projection": round(float(home_k_proj), 1),
                "away_projection": round(float(away_k_proj), 1),
                "source": "team k9 from baseball_stats.json",
                "data_tier": 1,
            }'''

NEW_E = '''                "home_projection": round(float(home_k_proj), 1),
                "away_projection": round(float(away_k_proj), 1),
                "source": ("starter K/9 over capped innings + staff K/9 for relief"
                           if (home_capped or away_capped)
                           else "team k9 from baseball_stats.json"),
                # A capped start is a guess about a decision a manager has not
                # made yet. Say so on the prop rather than letting the number
                # read like a normal projection.
                "caution": ("Starter on a pitch limit -- actual length depends "
                            "on the manager and pitch efficiency, so this "
                            "projection carries much wider error than usual. "
                            "Do not bet a strikeout prop off it."
                            if (home_capped or away_capped) else None),
                "data_tier": 3 if (home_capped or away_capped) else 1,
            }'''

pm = sub(pm, OLD_E, NEW_E, "E: strikeout caution")

# --- F. F5 window respects the cap ---------------------------------------
OLD_F = """            sp_home_era = home_sp_overrides.get("era", home_stats.get("era", 4.2)) if home_sp_overrides else home_stats.get("era", 4.2)
            sp_away_era = away_sp_overrides.get("era", away_stats.get("era", 4.2)) if away_sp_overrides else away_stats.get("era", 4.2)"""

NEW_F = '''            sp_home_era = home_sp_overrides.get("era", home_stats.get("era", 4.2)) if home_sp_overrides else home_stats.get("era", 4.2)
            sp_away_era = away_sp_overrides.get("era", away_stats.get("era", 4.2)) if away_sp_overrides else away_stats.get("era", 4.2)

            # F5 assumes the starters cover the first five. A 60-pitch cap is
            # about three and a half innings, so the bullpen is already in the
            # game before the F5 bet settles -- blend those innings in.
            _F5_IP = 5.0
            _h5 = min(home_sp_ip, _F5_IP)
            _a5 = min(away_sp_ip, _F5_IP)
            sp_home_era = _blended_era(float(sp_home_era), _pen["home_era"],
                                       _h5, _F5_IP - _h5)
            sp_away_era = _blended_era(float(sp_away_era), _pen["away_era"],
                                       _a5, _F5_IP - _a5)'''

pm = sub(pm, OLD_F, NEW_F, "F: F5 window")

save("predict_match.py", pm, pm_crlf)
print("[OK] predict_match.py  (6 edits)")


# ===========================================================================
# universal_runner.py -- accept the limit and pass raw K/9 through
# ===========================================================================
ur, ur_crlf = load("universal_runner.py")

if "home_sp_limit" in ur:
    raise SystemExit("ABORT: universal_runner.py already patched")

OLD_SIG = """def run_baseball(home: str, away: str, league: Optional[str], markets: Optional[List[str]], market_total: float,
                 home_sp_era: Optional[float], home_sp_k: Optional[float],
                 away_sp_era: Optional[float], away_sp_k: Optional[float],
                 store_to_db: bool, push_discord: bool,"""
NEW_SIG = """def run_baseball(home: str, away: str, league: Optional[str], markets: Optional[List[str]], market_total: float,
                 home_sp_era: Optional[float], home_sp_k: Optional[float],
                 away_sp_era: Optional[float], away_sp_k: Optional[float],
                 store_to_db: bool, push_discord: bool,
                 home_sp_limit: Optional[float] = None,
                 away_sp_limit: Optional[float] = None,"""
ur = sub(ur, OLD_SIG, NEW_SIG, "UR: signature")

OLD_H = """    home_sp_overrides = None
    if home_sp_era is not None or home_sp_k is not None:
        home_sp_overrides = {}
        if home_sp_era is not None:
            home_sp_overrides["era"] = float(home_sp_era)
        if home_sp_k is not None:
            home_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(home_sp_k) / batters_faced_est)
            )
"""
NEW_H = '''    home_sp_overrides = None
    if home_sp_era is not None or home_sp_k is not None or home_sp_limit is not None:
        home_sp_overrides = {}
        if home_sp_era is not None:
            home_sp_overrides["era"] = float(home_sp_era)
        if home_sp_k is not None:
            home_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(home_sp_k) / batters_faced_est)
            )
            # The prop model needs the rate per nine, not per batter faced.
            # Only k_rate was passed, so the starter never reached the
            # strikeout projection at all -- it used the staff rate for all
            # nine innings no matter who was pitching.
            home_sp_overrides["k9"] = float(home_sp_k)
        if home_sp_limit is not None:
            home_sp_overrides["pitch_limit"] = float(home_sp_limit)
'''
ur = sub(ur, OLD_H, NEW_H, "UR: home overrides")

OLD_AW = """    away_sp_overrides = None
    if away_sp_era is not None or away_sp_k is not None:
        away_sp_overrides = {}
        if away_sp_era is not None:
            away_sp_overrides["era"] = float(away_sp_era)
        if away_sp_k is not None:
            away_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(away_sp_k) / batters_faced_est)
            )
"""
NEW_AW = """    away_sp_overrides = None
    if away_sp_era is not None or away_sp_k is not None or away_sp_limit is not None:
        away_sp_overrides = {}
        if away_sp_era is not None:
            away_sp_overrides["era"] = float(away_sp_era)
        if away_sp_k is not None:
            away_sp_overrides["k_rate"] = max(
                0.0, min(0.60, float(away_sp_k) / batters_faced_est)
            )
            away_sp_overrides["k9"] = float(away_sp_k)
        if away_sp_limit is not None:
            away_sp_overrides["pitch_limit"] = float(away_sp_limit)
"""
ur = sub(ur, OLD_AW, NEW_AW, "UR: away overrides")

save("universal_runner.py", ur, ur_crlf)
print("[OK] universal_runner.py  (3 edits)")


# ===========================================================================
# run_mlb.py -- CLI flags
# ===========================================================================
rm, rm_crlf = load("run_mlb.py")

if "--home-sp-limit" in rm:
    raise SystemExit("ABORT: run_mlb.py already patched")

OLD_ARGS = '''    parser.add_argument("--odds", action="store_true",'''
NEW_ARGS = '''    parser.add_argument("--home-sp-limit", type=int, action="append", metavar="PITCHES",
                        help="Home starter is on a pitch count (e.g. 60). "
                             "Shortens his projected innings and hands the "
                             "rest to the bullpen. Repeatable, pairs with "
                             "--match in order.")
    parser.add_argument("--away-sp-limit", type=int, action="append", metavar="PITCHES",
                        help="Away starter is on a pitch count. Same rules.")
    parser.add_argument("--odds", action="store_true",'''
rm = sub(rm, OLD_ARGS, NEW_ARGS, "RM: args")

OLD_RUNONE = """def run_one(home: str, away: str, game: Optional[Dict[str, Any]], total: float,
            total_source: str, push_discord: bool, dry_run: bool,
            home_ml: Optional[int] = None,
            away_ml: Optional[int] = None) -> Dict[str, Any]:"""
NEW_RUNONE = """def run_one(home: str, away: str, game: Optional[Dict[str, Any]], total: float,
            total_source: str, push_discord: bool, dry_run: bool,
            home_ml: Optional[int] = None,
            away_ml: Optional[int] = None,
            home_sp_limit: Optional[int] = None,
            away_sp_limit: Optional[int] = None) -> Dict[str, Any]:"""
rm = sub(rm, OLD_RUNONE, NEW_RUNONE, "RM: run_one signature")

OLD_LOG = """    log(f"  Total      {total}  [{total_source}]")"""
NEW_LOG = '''    if home_sp_limit or away_sp_limit:
        log(f"  Pitch cap  {away} {away_sp_limit or 'none'}"
            f"  |  {home} {home_sp_limit or 'none'}")

    log(f"  Total      {total}  [{total_source}]")'''
rm = sub(rm, OLD_LOG, NEW_LOG, "RM: log line")

OLD_CALL = """    result = run_baseball(home, away, league=LEAGUE, markets=MARKETS,
                          market_total=total, store_to_db=True,
                          push_discord=push_discord,
                          home_ml=home_ml, away_ml=away_ml, **arguments)"""
NEW_CALL = """    result = run_baseball(home, away, league=LEAGUE, markets=MARKETS,
                          market_total=total, store_to_db=True,
                          push_discord=push_discord,
                          home_ml=home_ml, away_ml=away_ml,
                          home_sp_limit=home_sp_limit,
                          away_sp_limit=away_sp_limit, **arguments)"""
rm = sub(rm, OLD_CALL, NEW_CALL, "RM: run_baseball call")

OLD_PAIR = """    away_mls = pair_values(args.away_ml, len(pairs), "away-ml")"""
NEW_PAIR = """    away_mls = pair_values(args.away_ml, len(pairs), "away-ml")
    home_limits = pair_values(args.home_sp_limit, len(pairs), "home-sp-limit")
    away_limits = pair_values(args.away_sp_limit, len(pairs), "away-sp-limit")"""
rm = sub(rm, OLD_PAIR, NEW_PAIR, "RM: pair_values")

OLD_LOOP = """            outcomes.append(run_one(home, away, game, total, source,
                                    push_discord, args.dry_run,
                                    home_ml=home_ml, away_ml=away_ml))"""
NEW_LOOP = """            outcomes.append(run_one(home, away, game, total, source,
                                    push_discord, args.dry_run,
                                    home_ml=home_ml, away_ml=away_ml,
                                    home_sp_limit=home_limits[index],
                                    away_sp_limit=away_limits[index]))"""
rm = sub(rm, OLD_LOOP, NEW_LOOP, "RM: loop call")

save("run_mlb.py", rm, rm_crlf)
print("[OK] run_mlb.py  (6 edits)")
