#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mcp_server.py - Expose MultiSportPredict to Cline and Claude Desktop over MCP

WHAT THIS IS
    A local MCP server. It speaks JSON-RPC 2.0 over stdin/stdout, which is all
    the MCP "stdio" transport is. Point a client at it and the model's daily
    commands become tools that client can call in conversation.

WHY THERE ARE NO DEPENDENCIES
    The official `mcp` SDK would work, but it is a pip install that has to
    succeed inside the venv before anything runs at all, and a server that
    cannot start gives the client nothing to report except "failed". The stdio
    framing is one JSON object per line -- small enough to own outright, and
    owning it means this file runs under any Python 3.9+ with an empty
    environment.

WHY TOOLS SHELL OUT INSTEAD OF IMPORTING
    Every tool runs the existing script as a subprocess. Importing predict_match
    into this process would mean a missing scipy, a syntax error in a runner, or
    one bad season of data takes the whole server down at startup, and the
    client shows no tools at all. As a subprocess, a broken runner is one failed
    tool call with its stderr attached, and everything else still works.

THE ONE RULE
    stdout carries protocol frames and nothing else. Every diagnostic goes to
    stderr. A stray print() to stdout corrupts the stream and the client
    disconnects with no useful error -- this is the most common way a stdio MCP
    server dies.

RUN IT BY HAND (what the client does)
    venv/Scripts/python.exe mcp_server.py
    then paste:  {"jsonrpc":"2.0","id":1,"method":"tools/list"}

SELF TEST
    venv/Scripts/python.exe mcp_server.py --selftest
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# The client launches this file with the venv interpreter, so sys.executable is
# already the right Python for every subprocess. Hardcoding a path here would
# break the moment the venv is rebuilt.
PYTHON = sys.executable

SERVER_NAME = "multisportpredict"
SERVER_VERSION = "1.0.0"

# Versions this server knows how to speak. If the client asks for one of these
# we echo it back; otherwise we answer with our newest and let it decide.
KNOWN_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL = "2024-11-05"

# A model run on a full slate is slow. This is deliberately generous -- a tool
# that times out at 30s on a working command is worse than one that waits.
DEFAULT_TIMEOUT = 300


def log(message: str) -> None:
    """Diagnostics go to stderr. Never stdout. See THE ONE RULE above."""
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


# ==========================================================================
# RUNNING THE PROJECT'S OWN SCRIPTS
# ==========================================================================

def run_script(args: List[str], timeout: int = DEFAULT_TIMEOUT,
               env_overrides: Optional[Dict[str, str]] = None) -> str:
    """Run one of the project's scripts and return what a human would have seen.

    Returns combined output rather than raising on a non-zero exit, because the
    runners use exit codes to mean "I refused to predict from stale data" --
    which is an answer, not a failure, and the client should see the reason.
    """
    command = [PYTHON] + args
    log(f"run: {' '.join(args)}")
    try:
        # A shell variable beats .env (load_dotenv runs with override=False),
        # so passing one here retargets a single push without editing the file
        # or disturbing anything else the long-running bot is doing.
        done = subprocess.run(
            command, cwd=str(ROOT), capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
            env={**os.environ, **(env_overrides or {})},
        )
    except subprocess.TimeoutExpired:
        return (f"TIMED OUT after {timeout}s: {' '.join(args)}\n\n"
                f"The command was still running. Nothing was cancelled on disk -- "
                f"check the store or database before running it again.")
    except FileNotFoundError as exc:
        return f"COULD NOT START: {exc}"

    parts: List[str] = []
    if done.stdout.strip():
        parts.append(done.stdout.rstrip())
    if done.stderr.strip():
        parts.append("--- stderr ---\n" + done.stderr.rstrip())
    if done.returncode != 0:
        parts.append(f"--- exit code {done.returncode} ---")
    return "\n\n".join(parts) if parts else "(no output)"


def load_store(name: str) -> Dict[str, Any]:
    path = ROOT / "data" / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def records_of(store: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {k: v for k, v in store.items()
            if not k.startswith("_") and isinstance(v, dict)}


# ==========================================================================
# TOOLS
# ==========================================================================

def tool_list_teams(league: Optional[str] = None,
                    sport: str = "soccer") -> str:
    """What is actually seeded, so a prediction is never asked for on a club
    that is not in the store."""
    filename = {"soccer": "soccer_stats.json", "baseball": "baseball_stats.json",
                "nfl": "nfl_stats.json", "basketball": "euroleague_stats.json"}
    store = records_of(load_store(filename.get(sport, "soccer_stats.json")))
    if not store:
        return f"No {sport} store found, or it is empty."

    by_league: Dict[str, List[str]] = {}
    for team, record in store.items():
        by_league.setdefault(str(record.get("league", "?")), []).append(team)

    wanted = (league or "").strip().lower()
    lines: List[str] = []
    for name in sorted(by_league):
        if wanted and wanted not in name.lower():
            continue
        members = sorted(by_league[name])
        seasons = sorted({str(store[t].get("season", "?")) for t in members})
        lines.append(f"{name}  ({len(members)} teams, season {', '.join(seasons)})")
        for team in members:
            record = store[team]
            lines.append(f"    {team:<26} {record.get('goals_for', '?')} for / "
                         f"{record.get('goals_against', '?')} against  "
                         f"({record.get('games', '?')} games)")
    if not lines:
        return f"No league matching '{league}' in the {sport} store."
    return "\n".join(lines)


def tool_team_stats(team: str, sport: str = "soccer") -> str:
    filename = {"soccer": "soccer_stats.json", "baseball": "baseball_stats.json",
                "nfl": "nfl_stats.json", "basketball": "euroleague_stats.json"}
    store = records_of(load_store(filename.get(sport, "soccer_stats.json")))
    for name, record in store.items():
        if name.lower() == team.strip().lower():
            return f"{name}\n" + json.dumps(record, indent=2)

    close = [n for n in store if team.strip().lower() in n.lower()]
    if close:
        return (f"No exact match for '{team}'. Did you mean: "
                + ", ".join(sorted(close)) + "?")
    return (f"'{team}' is not in the {sport} store. Nothing was guessed -- "
            f"call list_teams to see what is seeded.")


def tool_check_data(sport: Optional[str] = None) -> str:
    args = ["data_guard.py"]
    if sport:
        args += ["--sport", sport]
    return run_script(args, timeout=120)


def tool_run_slate(slate: str, push: Optional[List[int]] = None,
                   dry_run: bool = False) -> str:
    """Run a slate file. Pushes nothing unless push indices are given."""
    slate_path = ROOT / slate
    if not slate_path.exists():
        available = sorted(p.name for p in ROOT.glob("slate*.json"))
        return (f"No slate file '{slate}'.\n"
                f"Slates present: {', '.join(available) or '(none)'}")
    args = ["run_soccer_batch.py", "--slate", slate]
    if dry_run:
        args.append("--dry-run")
    if push:
        args += ["--push"] + [str(int(n)) for n in push]
    return run_script(args)


def tool_run_mlb(match: List[str], total: Optional[float] = None,
                 no_discord: bool = True, league: str = "MLB") -> str:
    args = ["run_mlb.py", "--league", league]
    for one in match:
        args += ["--match", one]
    if total is not None:
        args += ["--total", str(total)]
    if no_discord:
        args.append("--no-discord")
    return run_script(args)


def tool_pending_results(days: Optional[int] = None,
                         sport: Optional[str] = None) -> str:
    args = ["grade_predictions.py", "--pending"]
    if days:
        args += ["--days", str(int(days))]
    if sport:
        args += ["--sport", sport]
    return run_script(args, timeout=120)


def tool_grade_results(csv_file: str = "pending_results.csv") -> str:
    if not (ROOT / csv_file).exists():
        return (f"No such file: {csv_file}. Call pending_results first -- it "
                f"writes the CSV with the games that still need scores.")
    return run_script(["grade_predictions.py", "--manual", csv_file, "--report"],
                      timeout=180)


def tool_record(sport: Optional[str] = None, days: Optional[int] = None) -> str:
    args = ["grade_predictions.py", "--report"]
    if sport:
        args += ["--sport", sport]
    if days:
        args += ["--days", str(int(days))]
    return run_script(args, timeout=120)


def tool_ingest(adapter: str, check_only: bool = False) -> str:
    args = ["ingest_all_sports.py", "--only", adapter]
    if check_only:
        args.append("--check")
    return run_script(args)


def tool_ingest_soccer(countries: str) -> str:
    return run_script(["ingest_soccer_fd.py", "--countries", countries])


def tool_list_players(search: str = "") -> str:
    store = ROOT / "data" / "tennis" / "players.json"
    if not store.exists():
        return ("No tennis store yet. Build it first with the ingest_tennis "
                "tool, or: python ingest_tennis.py")
    players = json.loads(store.read_text(encoding="utf-8-sig"))
    needle = search.strip().lower()
    hits = {n: r for n, r in players.items() if needle in n.lower()} if needle \
        else players
    if not hits:
        return f"Nobody matching '{search}' among {len(players)} players."
    lines = [f"{len(hits)} of {len(players)} players:"]
    for name in sorted(hits)[:60]:
        record = hits[name]
        thin = "" if record.get("enough_matches") else \
            f"   <- only {record.get('matches')} matches, rating not meaningful"
        lines.append(f"  {name:<26} {str(record.get('tour', '?')).upper():<4} "
                     f"{record.get('wins')}-{record.get('losses')}  "
                     f"rank {record.get('last_rank') or '?':<5} "
                     f"last {record.get('last_seen')}{thin}")
    if len(hits) > 60:
        lines.append(f"  ... and {len(hits) - 60} more")
    return "\n".join(lines)


def tool_run_tennis(match: List[str], surface: str = "hard",
                    tournament: str = "US Open", round_name: str = "R1",
                    p1_ml: Optional[List[float]] = None,
                    p2_ml: Optional[List[float]] = None,
                    dry_run: bool = False) -> str:
    args = ["run_tennis.py", "--surface", surface,
            "--tournament", tournament, "--round", round_name]
    for one in match:
        args += ["--match", one]
    for odds in (p1_ml or []):
        args += ["--p1-ml", str(odds)]
    for odds in (p2_ml or []):
        args += ["--p2-ml", str(odds)]
    if dry_run:
        args.append("--dry-run")
    return run_script(args)


def tool_ingest_tennis(years: Optional[List[int]] = None,
                       tours: Optional[List[str]] = None,
                       check_only: bool = False) -> str:
    args = ["ingest_tennis.py"]
    if years:
        args += ["--years"] + [str(int(y)) for y in years]
    if tours:
        args += ["--tours"] + list(tours)
    if check_only:
        args.append("--check")
    return run_script(args, timeout=420)


PUSH_TARGETS = {"bot": "bot", "app": "bot",
                "web": "webhooks", "webhook": "webhooks", "webhooks": "webhooks",
                "all": "all", "both": "all"}


def _target_env(target: Optional[str]) -> Optional[Dict[str, str]]:
    if not target:
        return None
    resolved = PUSH_TARGETS.get(str(target).strip().lower())
    if resolved is None:
        raise ValueError(f"Unknown destination '{target}'. Use one of: "
                         + ", ".join(sorted(set(PUSH_TARGETS))))
    return {"DISCORD_PUSH_TARGET": resolved}


def tool_push_tennis(indices: List[int], target: Optional[str] = None) -> str:
    review = ROOT / "data" / "tennis_review.json"
    if not review.exists():
        return ("Nothing to push -- no tennis review on file. Run the matches "
                "first; --push reads its results from there.")
    if not indices:
        return "No indices given. Pass the line numbers from the review table."
    return run_script(["run_tennis.py", "--push"]
                      + [str(int(n)) for n in indices], timeout=180,
                      env_overrides=_target_env(target))


def tool_push_to_discord(indices: List[int], target: Optional[str] = None) -> str:
    """Push reviewed predictions from the last slate run.

    Reads data/batch_review.json, which only exists after a slate has been run,
    so this cannot post a prediction that was never produced and reviewed.
    """
    review = ROOT / "data" / "batch_review.json"
    if not review.exists():
        return ("Nothing to push -- data/batch_review.json does not exist. "
                "Run a slate first; --push reads its results from there.")
    if not indices:
        return "No indices given. Pass the line numbers from the review table."
    return run_script(["run_soccer_batch.py", "--push"]
                      + [str(int(n)) for n in indices], timeout=180,
                      env_overrides=_target_env(target))


# name -> (schema, handler)
TOOLS: Dict[str, Dict[str, Any]] = {
    "list_teams": {
        "description": "List the teams currently seeded in a sport's store, "
                       "grouped by league, with their per-game numbers and "
                       "games played. Use this before predicting to confirm a "
                       "club is actually in the store.",
        "schema": {
            "type": "object",
            "properties": {
                "sport": {"type": "string",
                          "enum": ["soccer", "baseball", "nfl", "basketball"],
                          "description": "Which store to read. Default soccer."},
                "league": {"type": "string",
                           "description": "Optional filter, e.g. 'MLS', 'Serie A'."},
            },
        },
        "handler": tool_list_teams,
    },
    "team_stats": {
        "description": "Show one team's full stored record, including season, "
                       "games played, data tier and source. Returns near "
                       "matches rather than guessing when the name is wrong.",
        "schema": {
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "Team name as stored."},
                "sport": {"type": "string",
                          "enum": ["soccer", "baseball", "nfl", "basketball"]},
            },
            "required": ["team"],
        },
        "handler": tool_team_stats,
    },
    "check_data": {
        "description": "Audit every store for wrong-season, thin-sample and "
                       "stale records. Run this before trusting a prediction.",
        "schema": {
            "type": "object",
            "properties": {
                "sport": {"type": "string",
                          "enum": ["soccer", "baseball", "nfl", "basketball"]},
            },
        },
        "handler": tool_check_data,
    },
    "run_slate": {
        "description": "Run a soccer slate JSON through the model and print the "
                       "model-vs-market comparison table with the vig removed. "
                       "Pushes nothing to Discord unless push indices are given.",
        "schema": {
            "type": "object",
            "properties": {
                "slate": {"type": "string",
                          "description": "Slate filename, e.g. 'slate_mls.json'."},
                "push": {"type": "array", "items": {"type": "integer"},
                         "description": "Line numbers from the review table to "
                                        "push to Discord. Omit to push nothing."},
                "dry_run": {"type": "boolean",
                            "description": "Resolve team names only, predict nothing."},
            },
            "required": ["slate"],
        },
        "handler": tool_run_slate,
    },
    "run_mlb": {
        "description": "Run one or more MLB matchups through the model. "
                       "Format each as 'Home vs Away'.",
        "schema": {
            "type": "object",
            "properties": {
                "match": {"type": "array", "items": {"type": "string"},
                          "description": "e.g. ['Milwaukee Brewers vs Texas Rangers']"},
                "total": {"type": "number", "description": "Market total."},
                "no_discord": {"type": "boolean",
                               "description": "Default true. Set false to push."},
                "league": {"type": "string", "enum": ["MLB", "KBO"],
                           "description": "Which league in baseball_stats.json."},
            },
            "required": ["match"],
        },
        "handler": tool_run_mlb,
    },
    "pending_results": {
        "description": "List predictions still awaiting a final score and write "
                       "pending_results.csv for filling in.",
        "schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Look back this many days."},
                "sport": {"type": "string"},
            },
        },
        "handler": tool_pending_results,
    },
    "grade_results": {
        "description": "Grade predictions from a filled-in results CSV and print "
                       "the updated record.",
        "schema": {
            "type": "object",
            "properties": {
                "csv_file": {"type": "string",
                             "description": "Default 'pending_results.csv'."},
            },
        },
        "handler": tool_grade_results,
    },
    "record": {
        "description": "Print the win-rate and unit record: actual bets separated "
                       "from passes and informational rows, broken out by sport, "
                       "market and confidence band.",
        "schema": {
            "type": "object",
            "properties": {
                "sport": {"type": "string"},
                "days": {"type": "integer"},
            },
        },
        "handler": tool_record,
    },
    "ingest": {
        "description": "Run one daily ingestion adapter to refresh a store. "
                       "Adapters: mlb, mlb-probables, mlb-players, kbo, "
                       "euroleague, kbl, nznbl, tennis, soccer-espn, soccer.",
        "schema": {
            "type": "object",
            "properties": {
                "adapter": {"type": "string", "description": "Adapter name."},
                "check_only": {"type": "boolean",
                               "description": "Fetch and report, write nothing."},
            },
            "required": ["adapter"],
        },
        "handler": tool_ingest,
    },
    "ingest_soccer": {
        "description": "Refresh soccer team stats from football-data.co.uk for "
                       "one or more countries, e.g. 'england,italy,mexico'.",
        "schema": {
            "type": "object",
            "properties": {
                "countries": {"type": "string",
                              "description": "Comma-separated country names."},
            },
            "required": ["countries"],
        },
        "handler": tool_ingest_soccer,
    },
    "list_players": {
        "description": "List tennis players in the store with their record, "
                       "ranking and last match date. Flags anyone whose Elo "
                       "rests on too few matches to mean anything.",
        "schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string",
                           "description": "Filter by part of a name. Omit for all."},
            },
        },
        "handler": tool_list_players,
    },
    "run_tennis": {
        "description": "Run tennis matches through the surface-split Elo model. "
                       "Accepts real names ('Carlos Alcaraz') or the feed's "
                       "format ('Alcaraz C.'). Best-of-5 vs best-of-3 is read "
                       "from the player's tour. Pushes nothing to Discord.",
        "schema": {
            "type": "object",
            "properties": {
                "match": {"type": "array", "items": {"type": "string"},
                          "description": "e.g. ['Carlos Alcaraz vs Taylor Fritz']"},
                "surface": {"type": "string",
                            "enum": ["hard", "clay", "grass", "carpet"]},
                "tournament": {"type": "string", "description": "Default 'US Open'."},
                "round_name": {"type": "string", "description": "e.g. 'R1', 'QF'."},
                "p1_ml": {"type": "array", "items": {"type": "number"},
                          "description": "American odds for the first player, "
                                         "one per match, in the same order."},
                "p2_ml": {"type": "array", "items": {"type": "number"}},
                "dry_run": {"type": "boolean",
                            "description": "Resolve names only, predict nothing."},
            },
            "required": ["match"],
        },
        "handler": tool_run_tennis,
    },
    "ingest_tennis": {
        "description": "Rebuild the ATP/WTA match history and player store from "
                       "tennis-data.co.uk season archives. Slow -- it downloads "
                       "one archive per tour per season.",
        "schema": {
            "type": "object",
            "properties": {
                "years": {"type": "array", "items": {"type": "integer"},
                          "description": "Seasons to pull. Default 2025 and 2026."},
                "tours": {"type": "array", "items": {"type": "string",
                                                     "enum": ["atp", "wta"]}},
                "check_only": {"type": "boolean",
                               "description": "Download and report, write nothing."},
            },
        },
        "handler": tool_ingest_tennis,
    },
    "push_tennis": {
        "description": "Push reviewed tennis predictions to Discord by their "
                       "line number in the last run_tennis review table.",
        "schema": {
            "type": "object",
            "properties": {
                "indices": {"type": "array", "items": {"type": "integer"}},
                "target": {"type": "string",
                           "enum": ["bot", "webhooks", "all"],
                           "description": "Where to send it. Omit for .env."},
            },
            "required": ["indices"],
        },
        "handler": tool_push_tennis,
    },
    "push_to_discord": {
        "description": "Push reviewed SOCCER predictions to Discord by their line number "
                       "in the last slate review table. Only works after a slate "
                       "has been run -- it cannot post a prediction that was "
                       "never produced.",
        "schema": {
            "type": "object",
            "properties": {
                "indices": {"type": "array", "items": {"type": "integer"},
                            "description": "Line numbers from the review table."},
            },
            "required": ["indices"],
        },
        "handler": tool_push_to_discord,
    },
}


# ==========================================================================
# JSON-RPC / MCP PLUMBING
# ==========================================================================

def result(request_id: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def text_result(request_id: Any, text: str, is_error: bool = False) -> Dict[str, Any]:
    return result(request_id, {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    })


def handle(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a response frame, or None for notifications (which get no reply)."""
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    # Notifications carry no id and must never be answered.
    if request_id is None:
        log(f"notification: {method}")
        return None

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in KNOWN_PROTOCOLS else DEFAULT_PROTOCOL
        log(f"initialize (client asked {asked!r}, answering {version!r})")
        return result(request_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "ping":
        return result(request_id, {})

    if method == "tools/list":
        return result(request_id, {"tools": [
            {"name": name, "description": spec["description"],
             "inputSchema": spec["schema"]}
            for name, spec in TOOLS.items()
        ]})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        spec = TOOLS.get(name)
        if spec is None:
            return text_result(request_id,
                               f"Unknown tool '{name}'. Available: "
                               + ", ".join(sorted(TOOLS)), is_error=True)
        handler: Callable[..., str] = spec["handler"]
        try:
            return text_result(request_id, handler(**arguments))
        except TypeError as exc:
            return text_result(request_id,
                               f"Bad arguments for '{name}': {exc}", is_error=True)
        except Exception as exc:  # noqa: BLE001
            log(f"tool '{name}' raised {type(exc).__name__}: {exc}")
            return text_result(request_id,
                               f"{name} failed: {type(exc).__name__}: {exc}",
                               is_error=True)

    # resources/ and prompts/ are optional; say so properly rather than hanging.
    return error(request_id, -32601, f"Method not found: {method}")


def serve() -> None:
    log(f"ready in {ROOT} using {PYTHON}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"unparseable frame: {exc}")
            continue

        try:
            response = handle(message)
        except Exception as exc:  # noqa: BLE001
            log(f"handler crashed: {type(exc).__name__}: {exc}")
            response = error(message.get("id"), -32603, str(exc))

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    log("stdin closed, exiting")


def selftest() -> int:
    """Exercise the protocol the way a client does, without a client."""
    frames = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "selftest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "list_teams", "arguments": {"league": "MLS"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "team_stats",
                    "arguments": {"team": "Portland Timbers"}}},
    ]
    failures = 0
    for frame in frames:
        response = handle(frame)
        label = frame.get("method")
        if frame.get("id") is None:
            print(f"  ok    {label} (notification, no reply)")
            continue
        if response is None or "error" in response:
            print(f"  FAIL  {label}: {response}")
            failures += 1
            continue
        if label == "tools/list":
            names = [t["name"] for t in response["result"]["tools"]]
            print(f"  ok    tools/list -> {len(names)} tools: {', '.join(names)}")
        elif label == "tools/call":
            body = response["result"]["content"][0]["text"]
            first = body.splitlines()[0] if body.splitlines() else "(empty)"
            flag = "FAIL" if response["result"].get("isError") else "ok  "
            failures += 1 if response["result"].get("isError") else 0
            print(f"  {flag}  {frame['params']['name']} -> {first}")
        else:
            print(f"  ok    {label} -> {response['result'].get('serverInfo', {})}")
    print(f"\n{'FAILED' if failures else 'PASSED'} "
          f"({failures} failure(s), {len(TOOLS)} tools registered)")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    serve()
