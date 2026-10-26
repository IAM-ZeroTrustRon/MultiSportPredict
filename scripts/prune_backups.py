"""Prune routine hourly grading snapshots; never touch a milestone backup.

Every `msp.py grade` pass writes a full database copy under
output/workflow/grade_<YYYYMMDD>_<HHMMSS>/. At hourly cadence that is roughly
115 MB/day, so the routine ones are rotated.

Only that exact routine pattern is eligible. Everything else in the same
folder -- refresh_*, task2_*, takeover_*, the manual pre-backfill snapshots
under output/backups -- is a milestone and is preserved regardless of age.
Deleting is irreversible, so the default is a dry run and every removal is
logged.

Usage:
    venv/Scripts/python.exe -u scripts/prune_backups.py --dry-run
    venv/Scripts/python.exe -u scripts/prune_backups.py            # keep 72
    venv/Scripts/python.exe -u scripts/prune_backups.py --keep 24
"""
import argparse
import datetime as dt
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "output" / "workflow"
LOG = ROOT / "logs" / "backup_prune.log"
ROUTINE = re.compile(r"^grade_\d{8}_\d{6}$")
DEFAULT_KEEP = 72          # 3 days at hourly cadence


def routine_snapshots(root=WORKFLOW):
    """Only directories that match the hourly grading snapshot pattern."""
    if not root.is_dir():
        return []
    found = [d for d in root.iterdir() if d.is_dir() and ROUTINE.match(d.name)]
    return sorted(found, key=lambda d: d.name)


def protected(root=WORKFLOW):
    """Everything else in the folder, listed so the log proves what was kept."""
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and not ROUTINE.match(d.name))


def prune(keep=DEFAULT_KEEP, dry_run=True, root=WORKFLOW):
    if keep < 1:
        raise ValueError("keep must be at least 1")
    resolved_root = root.resolve()
    snapshots = routine_snapshots(root)
    removable = snapshots[:-keep] if len(snapshots) > keep else []
    removed, freed = [], 0
    for directory in removable:
        # Defence in depth: refuse anything not directly inside the workflow
        # folder, even if the regex somehow matched it.
        if directory.resolve().parent != resolved_root:
            continue
        size = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
        removed.append((directory.name, size))
        freed += size
        if not dry_run:
            shutil.rmtree(directory)
    return dict(
        routine=len(snapshots), kept=len(snapshots) - len(removable),
        removed=removed, freed_bytes=freed, dry_run=dry_run,
        protected=protected(root), keep=keep)


def log_result(result):
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    freed = result["freed_bytes"] / (1024 * 1024)
    lines = [f"[{stamp}] {'DRY RUN ' if result['dry_run'] else ''}"
             f"routine={result['routine']} kept={result['kept']} "
             f"removed={len(result['removed'])} freed={freed:.1f}MB"]
    for name, size in result["removed"]:
        lines.append(f"    removed {name} ({size / (1024 * 1024):.1f}MB)")
    if result["protected"]:
        lines.append("    preserved: " + ", ".join(result["protected"][:12])
                     + (" ..." if len(result["protected"]) > 12 else ""))
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"routine snapshots to keep (default {DEFAULT_KEEP})")
    parser.add_argument("--dry-run", action="store_true", help="report without deleting")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    result = prune(keep=args.keep, dry_run=args.dry_run)
    log_result(result)
    if not args.quiet:
        print(f"{'DRY RUN: ' if args.dry_run else ''}routine snapshots {result['routine']}, "
              f"kept {result['kept']}, removed {len(result['removed'])}, "
              f"freed {result['freed_bytes'] / (1024 * 1024):.1f} MB")
        if result["protected"]:
            print(f"preserved {len(result['protected'])} non-routine folder(s): "
                  + ", ".join(result["protected"][:8])
                  + (" ..." if len(result["protected"]) > 8 else ""))
    return result


if __name__ == "__main__":
    main()
