#!/usr/bin/env python
"""push_research.py - push a /research card to Discord.

The /research command writes a card to output/research/cards/<name>.json.
This script checks it against Discord's limits and sends it through the same
broadcaster every other push uses (_broadcast_embed), so DISCORD_PUSH_TARGET,
deduplication and the bot/webhook settings in .env all apply.

Research cards are not model output. The footer says so on every card, and
this script adds it if the card is missing it.

Run from Git Bash:
    python push_research.py --list                 # show saved cards
    python push_research.py <card.json> --dry-run  # check it, send nothing
    python push_research.py <card.json>            # send it
    python push_research.py --latest               # send the newest card
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CARDS = ROOT / "output" / "research" / "cards"
LABEL = "MultiSportPredict - RESEARCH, not a model pick"

# Discord embed limits.
MAX_TITLE, MAX_DESC, MAX_FIELDS = 256, 4096, 25
MAX_NAME, MAX_VALUE, MAX_TOTAL = 256, 1024, 6000


def problems(card: dict) -> list:
    out = []
    if not card.get("title"):
        out.append("missing title")
    if len(card.get("title", "")) > MAX_TITLE:
        out.append(f"title over {MAX_TITLE} chars")
    if len(card.get("description", "")) > MAX_DESC:
        out.append(f"description over {MAX_DESC} chars")
    fields = card.get("fields") or []
    if not fields:
        out.append("no fields")
    if len(fields) > MAX_FIELDS:
        out.append(f"{len(fields)} fields, limit {MAX_FIELDS}")
    for i, f in enumerate(fields, 1):
        if not f.get("name") or not f.get("value"):
            out.append(f"field {i} has an empty name or value")
        if len(f.get("name", "")) > MAX_NAME:
            out.append(f"field {i} name over {MAX_NAME}")
        if len(f.get("value", "")) > MAX_VALUE:
            out.append(f"field {i} ('{f.get('name')}') value over {MAX_VALUE}")
    if len(json.dumps(card)) > MAX_TOTAL:
        out.append(f"card is {len(json.dumps(card))} chars, limit {MAX_TOTAL}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("card", nargs="?", type=Path)
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.list:
        for p in sorted(CARDS.glob("*.json")):
            print(p.relative_to(ROOT))
        return

    path = args.card
    if args.latest:
        found = sorted(CARDS.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not found:
            sys.exit(f"No cards in {CARDS.relative_to(ROOT)}")
        path = found[-1]
    if not path:
        sys.exit("Give a card path, or --latest, or --list.")
    if not path.exists() and (CARDS / path.name).exists():
        path = CARDS / path.name
    if not path.exists():
        sys.exit(f"Card not found: {path}")

    card = json.loads(path.read_text(encoding="utf-8-sig"))
    card.setdefault("footer", {})["text"] = LABEL

    bad = problems(card)
    if bad:
        print("[REFUSED] Card not sent:")
        for b in bad:
            print(f"  - {b}")
        sys.exit(1)

    print(f"Card: {path.name}")
    print(f"  {card['title']}")
    print(f"  {len(card['fields'])} fields, {len(json.dumps(card))} chars")

    if args.dry_run:
        print(json.dumps(card, indent=2))
        print("\n--dry-run: nothing sent.")
        return

    from discord_integration import _broadcast_embed   # only needed to send
    sent = _broadcast_embed(card, label=f"research {path.stem}")
    print(f"Sent to {sent} destination(s)." if sent else
          "Nothing sent - check DISCORD_WEBHOOK_URL / bot settings in .env.")


if __name__ == "__main__":
    main()
