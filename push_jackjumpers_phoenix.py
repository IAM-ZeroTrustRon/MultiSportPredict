#!/usr/bin/env python
"""push_jackjumpers_phoenix.py - push the NBL27 R1 research card to Discord.

This is NOT model output. MultiSportPredict has no Australian NBL engine and
no team data for this league, so running it through the model would produce
league-average numbers dressed up as a prediction. The card says so.

Run from Git Bash:
    python push_jackjumpers_phoenix.py --dry-run   # print the card, send nothing
    python push_jackjumpers_phoenix.py             # send it
"""
import argparse
import json


EMBED = {
    "title": "NBL27 R1 | Tasmania JackJumpers vs SE Melbourne Phoenix",
    "description": (
        "**RESEARCH CARD - not model output.** The model has no Australian NBL "
        "engine yet.\n"
        "Mon 21 Sep - 5:30am ET - MyState Bank Arena, Hobart"
    ),
    "color": 0x2B6CB0,
    "fields": [
        {"name": "Market", "inline": False, "value": (
            "Line: TAS +3.5 / PHX -3.5\n"
            "Total: 185.5\n"
            "1Q (bet365): TAS +0.5 +100 | O/U 47.5 -112/-118\n"
            "1Q team totals: TAS 23.5 | PHX 24.5 (O -105 / U -125)")},
        {"name": "Best bet", "inline": False, "value": (
            "**PHX 1Q team total UNDER 24.5 (-125)**\n"
            "Break-even 55.6%. Projection: PHX ~22.")},
        {"name": "Leans", "inline": False, "value": (
            "- TAS +3.5 (full game)\n"
            "- Under 185.5 (full game)\n"
            "- 1Q Under 47.5 (-118) - pick this OR the PHX team under, not both\n"
            "- TAS 1Q +0.5 (+100) - small")},
        {"name": "Why", "inline": False, "value": (
            "- PHX played Sat in Perth, now Hobart ~48h later\n"
            "- PHX lost the 1Q 19-24 in Perth on fresh legs\n"
            "- Last season: TAS won the slow games (170, 171 pts), "
            "PHX won the fast ones (205, 224)\n"
            "- Roth held PHX to 81 and 84 in his two wins")},
        {"name": "Check before betting", "inline": False, "value": (
            "- Josh Bannan (TAS, ribs) - TEST\n"
            "- Nathan Sobey (PHX, back) - TBC\n"
            "- Bryce Hamilton (TAS) - OUT (ACL)")},
        {"name": "Against", "inline": False, "value": (
            "TAS 6-10 at home last season, 0-2 in preseason. "
            "Majok Deng scored 36 (20 in the 1Q) vs PHX last meeting.")},
        {"name": "Confidence", "inline": True, "value": "Low - Round 1, one game of data"},
        {"name": "Sharp data", "inline": True, "value": "None exists for this league"},
    ],
    "footer": {"text": "MultiSportPredict - research, not a model pick"},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print(json.dumps(EMBED, indent=2))
        print(f"\nfields: {len(EMBED['fields'])}  "
              f"chars: {len(json.dumps(EMBED))}  (Discord limit 6000)")
        return

    from discord_integration import _broadcast_embed   # only needed to send
    sent = _broadcast_embed(EMBED, label="NBL27 R1 TAS v PHX research")
    print(f"Sent to {sent} destination(s)." if sent else
          "Nothing was sent - check .env for DISCORD_WEBHOOK_URL / bot settings.")


if __name__ == "__main__":
    main()
