#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cleanup_repo.py - Tidy the MultiSportPredict root without breaking anything.

The root holds ~330 loose files. About 250 of them are one-off scripts from
single games in June and July, .bak copies, scratch JSON and old reports. The
~45 files that actually run the model are buried among them.

This moves the dead weight into archive/ and leaves the working set at root.
Nothing is deleted. Nothing is renamed. No import path changes.

HOW IT DECIDES WHAT TO KEEP
---------------------------
It does not trust a hand-written list of "important files". It starts from the
entry points you actually run, parses their imports, follows those imports into
the files they import, and keeps everything it reaches. A module is archived
only if nothing reachable from an entry point imports it.

That is the whole safety argument: if a file is needed, something imports it,
so it is kept.

USAGE
-----
    python cleanup_repo.py                # dry run - prints the plan, moves nothing
    python cleanup_repo.py --apply        # do it
    python cleanup_repo.py --apply --no-git   # plain mv instead of git mv

Run the dry run first and read it.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# The things you actually run. Everything these reach, directly or through a
# chain of imports, stays at root.
# --------------------------------------------------------------------------
ENTRY_POINTS = [
    "run_mlb.py", "run_nfl.py", "run_tennis.py", "run_soccer_batch.py",
    "run_tonight.py", "run_liga_mx.py", "batch_tennis.py",
    "run_match.py", "run_match_safe.py",
    "universal_runner.py", "predict_match.py",
    "grade_predictions.py", "import_picks.py", "backtest_report.py",
    "ingest_all_sports.py", "ingest_mlb.py", "ingest_nfl.py",
    "ingest_nfl_schedule.py", "ingest_ncaaf.py", "ingest_tennis.py",
    "ingest_soccer.py", "ingest_soccer_espn.py", "ingest_soccer_fd.py",
    "ingest_soccer_global.py", "ingest_hoops.py", "ingest_intl_hoops.py",
    "ingest_mlb_props.py", "ingest_schedules.py",
    "auto_mlb_scraper.py", "kbo_scraper.py",
    "discord_integration.py", "embed_builder.py", "msp_bot.py", "mcp_server.py",
    "data_guard.py", "fixture_guard.py", "team_stats_provider.py",
    "live_odds.py", "probe_sources.py", "diagnose_sources.py",
    "config.py", "app.py",
]

# Never moved, whatever the import graph says.
PROTECTED = {
    "cleanup_repo.py", "requirements.txt", "config.json",
    "README.md", "STATE.md", "START_HERE.md", "COMMANDS.md", "RON_RUNBOOK.md",
    "msp", "run.bat", "run.ps1", "refresh_all.bat", "refresh_all.sh",
    "start_bot.bat", "install_daily_task.bat", "push_to_github.bat",
    "run_diagnostic.bat",
    "multisport_history.db", "pending_results.csv",
    ".env", ".env.example", ".gitignore", ".gitattributes", ".gitkeep",
}

# Reference docs worth keeping, just not at the root.
TO_DOCS = {
    "ARCHITECTURE.md", "DAILY_INGESTION.md", "RESULTS_TRACKING.md",
    "MCP_SETUP.md", "MOBILE_SETUP.md", "SOCCER_LEAGUE_CONFIG.md",
    "DISCORD_SETUP.md", "DISCORD_README.md", "DISCORD_QUICKSTART.md",
    "DISCORD_CHECKLIST.md", "DISCORD_INTEGRATION_GUIDE.md",
    "NFL_ENGINE_PLAN.md", "AUTOMATED_PREDICTIONS.md", "TODO.md",
}


def classify(name: str) -> str:
    """Which archive bucket a leftover file belongs in.

    Extension is checked before the name prefix: test_tennis_final.db is a
    database, not a test script, and the prefix rule would have filed it with
    the scripts.
    """
    low = name.lower()
    if ".bak" in low:
        return "archive/backups"
    if name.endswith((".db", ".sqlite", ".sqlite3")):
        return "archive/scratch-data"
    if name.endswith((".txt", ".log")):
        return "archive/scratch"
    if low.startswith(("patch_", "fix_", "add_debug", "phase")) or low.startswith("recalibrate_"):
        return "archive/patches"
    if low.startswith("push_") or "to_discord" in low:
        return "archive/discord-pushes"
    if low.startswith("run_") or low.startswith("tmp_"):
        return "archive/one-off-runs"
    if low.startswith(("check_", "scan_", "scrape_", "seed_", "explore_",
                       "fetch_cincinnati", "compile_", "test_")):
        return "archive/scratch-scripts"
    if name.endswith((".md", ".pdf")):
        return "archive/reports"
    if name.endswith((".txt", ".log")):
        return "archive/scratch"
    if name.endswith((".json", ".db")):
        return "archive/scratch-data"
    if name.endswith(".py"):
        return "archive/legacy-modules"
    return "archive/misc"


def local_imports(path: Path, known: Set[str]) -> Set[str]:
    """Module names this file imports that exist as local .py files or packages."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return set()
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                found.add(node.module.split(".")[0])
    return {m for m in found if m in known}


def build_keep_set() -> Set[str]:
    """Entry points plus everything reachable from them through imports."""
    modules = {p.stem: p.name for p in ROOT.glob("*.py")}
    packages = {d.name for d in ROOT.iterdir()
                if d.is_dir() and (d / "__init__.py").exists()}
    known = set(modules) | packages

    keep: Set[str] = set()
    queue: List[str] = [e for e in ENTRY_POINTS if (ROOT / e).exists()]
    seen: Set[str] = set()

    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        keep.add(name)
        path = ROOT / name
        if not path.exists():
            continue
        for module in local_imports(path, known):
            if module in packages:
                keep.add(module)
                # follow imports inside the package too
                for sub in (ROOT / module).rglob("*.py"):
                    for m2 in local_imports(sub, known):
                        if m2 in modules and modules[m2] not in seen:
                            queue.append(modules[m2])
            elif module in modules and modules[module] not in seen:
                queue.append(modules[module])
    return keep


def git_tracked() -> Set[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return set(out.splitlines())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Actually move files.")
    ap.add_argument("--no-git", action="store_true",
                    help="Use plain mv even for tracked files.")
    args = ap.parse_args()

    keep = build_keep_set()
    tracked = git_tracked()

    plan: Dict[str, List[str]] = {}
    for entry in sorted(ROOT.iterdir()):
        if entry.is_dir() or entry.name.startswith("."):
            continue
        name = entry.name
        if name in PROTECTED or name in keep:
            continue
        dest = "docs" if name in TO_DOCS else classify(name)
        plan.setdefault(dest, []).append(name)

    total = sum(len(v) for v in plan.values())
    root_files = sum(1 for p in ROOT.iterdir()
                     if p.is_file() and not p.name.startswith("."))

    print("=" * 74)
    print("  CLEANUP PLAN" + ("" if args.apply else "   (DRY RUN - nothing will move)"))
    print("=" * 74)
    print(f"  root files now : {root_files}")
    print(f"  to archive     : {total}")
    print(f"  left at root   : {root_files - total}")
    print(f"  kept by import graph: {len(keep)} module(s)")
    print()

    for dest in sorted(plan):
        names = plan[dest]
        print(f"  {dest}/   ({len(names)} files)")
        for n in names[:6]:
            print(f"      {n}")
        if len(names) > 6:
            print(f"      ... and {len(names) - 6} more")
        print()

    if not args.apply:
        print("  Nothing moved. Re-run with --apply to do it.")
        print("=" * 74)
        return

    moved = failed = 0
    for dest, names in plan.items():
        (ROOT / dest).mkdir(parents=True, exist_ok=True)
        for name in names:
            src, dst = ROOT / name, ROOT / dest / name
            if dst.exists():
                print(f"  [skip] {name} - already in {dest}/")
                continue
            try:
                if name in tracked and not args.no_git:
                    subprocess.run(["git", "mv", name, f"{dest}/{name}"],
                                   cwd=ROOT, check=True, capture_output=True)
                else:
                    shutil.move(str(src), str(dst))
                moved += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  [FAIL] {name}: {exc}")
                failed += 1

    print(f"\n  moved {moved} file(s)" + (f", {failed} failed" if failed else ""))
    print("  Nothing was deleted. Everything is under archive/ or docs/.")

    # ---- verify nothing at root lost an import it needs -------------------
    print("\n  Checking every file left at root still parses and imports...")
    import py_compile
    broken: List[str] = []
    for p in sorted(ROOT.glob("*.py")):
        try:
            py_compile.compile(str(p), doraise=True, cfile=str(ROOT / "__pycache__" / (p.stem + ".chk")))
        except py_compile.PyCompileError as exc:
            broken.append(f"{p.name}: {exc}")
    still = {p.stem for p in ROOT.glob("*.py")}
    pkgs = {d.name for d in ROOT.iterdir() if d.is_dir()}
    missing: List[str] = []
    for p in sorted(ROOT.glob("*.py")):
        for mod in local_imports(p, still | pkgs | {m for m in plan.get("archive/one-off-runs", [])}):
            pass
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            for n in names:
                if (ROOT / f"{n}.py").exists() or n in pkgs:
                    continue
                for dest, moved_names in plan.items():
                    if f"{n}.py" in moved_names:
                        missing.append(f"{p.name} imports {n} -> moved to {dest}/")

    if broken:
        print("  [FAIL] files that no longer compile:")
        for b in broken:
            print(f"      {b}")
    if missing:
        print("  [FAIL] an import was archived out from under a file still at root:")
        for m in sorted(set(missing)):
            print(f"      {m}")
        print("\n  Move those back:  git mv archive/<bucket>/<file>.py .")
    if not broken and not missing:
        print("  OK - every root file compiles and every import it needs is still at root.")

    print("\n  Next:")
    print("    venv/Scripts/python.exe run_mlb.py --list-teams        # smoke test")
    print("    git add -A")
    print("    git commit -m \"Move one-off scripts, backups and scratch into archive/\"")
    print("=" * 74)


if __name__ == "__main__":
    main()
