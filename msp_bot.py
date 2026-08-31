#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
msp_bot.py - Run MultiSportPredict from your phone, through Discord

    venv/Scripts/python.exe msp_bot.py

WHY A BOT AND NOT SSH
    A Discord bot opens an OUTBOUND connection to Discord and keeps it. Nothing
    listens on your PC, no port is forwarded, no firewall rule changes, and your
    home IP is never published. From the phone's side you are just typing in an
    app you already have open. SSH would put a listening service on a Windows
    box exposed to the internet, which is a bigger thing to get right than it
    looks and a worse thing to get wrong.

WHAT IT REUSES
    Every command calls the same handler mcp_server.py exposes to Claude
    Desktop. Adding a capability in one place gives it to both. This file is a
    front end and nothing else -- it holds no model logic and no data access of
    its own.

SECURITY, BECAUSE THIS RUNS CODE ON YOUR PC
    * Two locks, both required: your Discord user ID AND one channel ID.
      A message failing either is dropped without a reply -- a bot that says
      "you are not authorised" tells a stranger the bot is real and listening.
    * No shell, ever. Commands are built as argument lists and handed to
      subprocess directly. There is no string for a ';' or a '&&' to break out
      of, so `!slate x.json; del *.*` is just a filename that does not exist.
    * Arguments are validated against what they are allowed to be, not scanned
      for what they are not: numbers must parse as integers, slate files must
      match a pattern AND already exist on disk, sports must be in a fixed set.
      Blocklists are a guess about attacks; allowlists are a statement about
      what is legal.
    * One job at a time. A held lock means a mashed command queues instead of
      forking twenty Python processes.
    * Input is length-capped and output is truncated before it is sent.

SETUP
    See MOBILE_SETUP.md. Three values go in .env, which is already gitignored:
        DISCORD_BOT_TOKEN=...
        DISCORD_OWNER_ID=...
        DISCORD_BOT_CHANNEL_ID=...
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

MAX_INPUT = 300           # characters of command text accepted
MAX_MESSAGES = 4          # chunks of output sent per command
CHUNK = 1900              # Discord's hard limit is 2000; leave room for fences

SLATE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}\.json$")
SPORTS = {"soccer", "baseball", "nfl", "basketball", "tennis", "mlb"}
SURFACES = {"hard", "clay", "grass", "carpet"}


# ==========================================================================
# CONFIG
# ==========================================================================

def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        print(f"[msp_bot] {name} is not set in .env -- refusing to start.\n"
              f"          A bot with no owner lock would take orders from anyone "
              f"who can see the channel.", file=sys.stderr)
        sys.exit(1)
    return value


def require_id(name: str) -> int:
    value = require(name)
    if not value.isdigit():
        print(f"[msp_bot] {name}={value!r} is not a numeric Discord ID.\n"
              f"          Turn on Settings > Advanced > Developer Mode, then "
              f"right-click and Copy ID.", file=sys.stderr)
        sys.exit(1)
    return int(value)


# ==========================================================================
# ARGUMENT VALIDATION
# ==========================================================================

class BadCommand(Exception):
    pass


def as_indices(parts: List[str]) -> List[int]:
    if not parts:
        raise BadCommand("Give at least one line number, e.g. `!push 1 3`")
    out: List[int] = []
    for part in parts:
        if not part.isdigit():
            raise BadCommand(f"`{part}` is not a line number.")
        number = int(part)
        if not 1 <= number <= 99:
            raise BadCommand(f"`{part}` is out of range (1-99).")
        out.append(number)
    return out


def as_slate(name: str) -> str:
    """A slate must look like a slate AND already exist.

    Existence is the real check. A name that passes the pattern but is not a
    file on disk is either a typo or someone probing, and both deserve the
    same answer: no.
    """
    if not SLATE_PATTERN.match(name):
        raise BadCommand(f"`{name}` is not a slate filename.")
    if not (ROOT / name).exists():
        available = sorted(p.name for p in ROOT.glob("slate*.json"))
        raise BadCommand(f"No slate `{name}`. Present: "
                         + (", ".join(f"`{a}`" for a in available) or "none"))
    return name


def as_sport(name: str) -> str:
    lowered = name.strip().lower()
    if lowered not in SPORTS:
        raise BadCommand(f"`{name}` is not a sport. One of: "
                         + ", ".join(sorted(SPORTS)))
    return lowered


def as_days(text: str) -> int:
    if not text.isdigit() or not 1 <= int(text) <= 365:
        raise BadCommand(f"`{text}` is not a day count (1-365).")
    return int(text)


def split_matchup(text: str) -> str:
    """Accept a matchup as free text but insist it names two sides.

    The text is never interpolated into a command line -- it becomes one
    argv element. This check is about catching a typo before spending a
    minute of model time, not about safety.
    """
    cleaned = " ".join(text.split())
    if not cleaned:
        raise BadCommand("Give a matchup, e.g. `Carlos Alcaraz vs Taylor Fritz`")
    if not re.search(r"\s(vs\.?|v\.?|@|-)\s", cleaned, flags=re.I):
        raise BadCommand(f"`{cleaned}` does not name two sides. "
                         f"Use `A vs B`.")
    return cleaned


def trailing_odds(text: str) -> Tuple[str, Optional[float], Optional[float]]:
    """Pull an optional '-450 +340' off the end of a matchup."""
    match = re.search(r"\s([+-]\d{3,5})\s+([+-]\d{3,5})\s*$", text)
    if not match:
        return text, None, None
    return text[:match.start()].strip(), float(match.group(1)), float(match.group(2))


# ==========================================================================
# COMMANDS
# ==========================================================================

import mcp_server as tools     # noqa: E402  -- after os.chdir, on purpose


def call(name: str, **kwargs: Any) -> str:
    return tools.TOOLS[name]["handler"](**kwargs)


def cmd_teams(args: List[str]) -> str:
    league = " ".join(args).strip()
    return call("list_teams", sport="soccer", league=league or None)


def cmd_team(args: List[str]) -> str:
    if not args:
        raise BadCommand("Name a team, e.g. `!team Portland Timbers`")
    return call("team_stats", team=" ".join(args))


def cmd_players(args: List[str]) -> str:
    return call("list_players", search=" ".join(args).strip())


def cmd_tennis(args: List[str]) -> str:
    text, odds1, odds2 = trailing_odds(" ".join(args))
    matchup = split_matchup(text)
    payload: Dict[str, Any] = {"match": [matchup], "surface": "hard"}
    if odds1 is not None and odds2 is not None:
        payload["p1_ml"] = [odds1]
        payload["p2_ml"] = [odds2]
    return call("run_tennis", **payload)


def cmd_mlb(args: List[str]) -> str:
    return call("run_mlb", match=[split_matchup(" ".join(args))])


def cmd_kbo(args: List[str]) -> str:
    """KBO rows live in the same store as MLB and differ only by league, so
    this is !mlb with the flag set rather than a second code path."""
    return call("run_mlb", match=[split_matchup(" ".join(args))], league="KBO")


def cmd_slate(args: List[str]) -> str:
    if not args:
        raise BadCommand("Name a slate, e.g. `!slate slate_mls.json`")
    return call("run_slate", slate=as_slate(args[0]))


def split_target(args: List[str]) -> Tuple[List[str], Optional[str]]:
    """Peel an optional destination word off the end: `!tpush 1 4 7 web`.

    Without this the only way to change where a pick goes was to edit .env at
    the PC -- which defeats the point of a phone command.
    """
    if args and not args[-1].isdigit():
        return args[:-1], args[-1]
    return args, None


def cmd_push(args: List[str]) -> str:
    numbers, target = split_target(args)
    return call("push_to_discord", indices=as_indices(numbers), target=target)


def cmd_tpush(args: List[str]) -> str:
    numbers, target = split_target(args)
    return call("push_tennis", indices=as_indices(numbers), target=target)



def cmd_record(args: List[str]) -> str:
    return call("record", sport=as_sport(args[0]) if args else None)


def cmd_pending(args: List[str]) -> str:
    return call("pending_results", days=as_days(args[0]) if args else None)


def cmd_check(args: List[str]) -> str:
    return call("check_data", sport=as_sport(args[0]) if args else None)


def cmd_help(_: List[str]) -> str:
    return (
        "MultiSportPredict\n"
        "\n"
        "  !tennis A vs B [-450 +340]   run a tennis match (odds optional)\n"
        "  !mlb Home vs Away            run an MLB game\n"
        "  !kbo Home vs Away            run a KBO game\n"
        "  !slate slate_mls.json        run a soccer slate\n"
        "\n"
        "  !push 1 3 [bot|web|all]      push those soccer lines\n"
        "  !tpush 1 4 7 [bot|web|all]   push those tennis lines\n"
        "     no destination = whatever .env says\n"
        "\n"
        "  !players alcaraz             search tennis players\n"
        "  !teams MLS                   teams in a league\n"
        "  !team Portland Timbers       one team's numbers\n"
        "\n"
        "  !check soccer                data guard: stale or thin\n"
        "  !record baseball             win rate and units\n"
        "  !pending 3                   what still needs a score\n"
        "\n"
        "Nothing reaches Discord until you !push it."
    )


COMMANDS: Dict[str, Callable[[List[str]], str]] = {
    "help": cmd_help, "tennis": cmd_tennis, "mlb": cmd_mlb, "kbo": cmd_kbo,
    "slate": cmd_slate,
    "push": cmd_push, "tpush": cmd_tpush, "players": cmd_players,
    "teams": cmd_teams, "team": cmd_team, "check": cmd_check,
    "record": cmd_record, "pending": cmd_pending,
}


# ==========================================================================
# DISCORD
# ==========================================================================

def chunks(text: str) -> List[str]:
    """Split output into fenced blocks Discord will accept."""
    lines = text.splitlines() or ["(no output)"]
    blocks: List[str] = []
    current = ""
    for line in lines:
        line = line[:CHUNK]
        if len(current) + len(line) + 1 > CHUNK:
            blocks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        blocks.append(current)
    if len(blocks) > MAX_MESSAGES:
        blocks = blocks[:MAX_MESSAGES]
        blocks[-1] += "\n... truncated. Full output is on the PC."
    return [f"```\n{b}\n```" for b in blocks]


def discover(token: str, discord: Any) -> None:
    """Print the two IDs the bot needs, so nobody has to hunt for a setting.

    Discord keeps moving Developer Mode around its settings tree. The IDs are
    attached to every message the bot already receives, so the bot is the most
    reliable place to read them from. Runs no commands and holds no owner lock,
    because it exists precisely for the moment before an owner is known.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        print(f"\n[discover] connected as {client.user}")
        print("[discover] now type anything in the channel you want to use.\n")

    @client.event
    async def on_message(message: Any) -> None:
        if message.author.bot:
            return
        print("=" * 62)
        print(f"  DISCORD_OWNER_ID={message.author.id}        <- {message.author}")
        print(f"  DISCORD_BOT_CHANNEL_ID={message.channel.id} <- #{message.channel}")
        print("=" * 62)
        print("  Put those two lines in .env, then Ctrl+C and run the bot normally.\n")
        try:
            await message.channel.send(
                f"```\nDISCORD_OWNER_ID={message.author.id}\n"
                f"DISCORD_BOT_CHANNEL_ID={message.channel.id}\n```")
        except Exception:                               # noqa: BLE001
            pass       # console output is the real answer; the reply is a bonus

    client.run(token, log_handler=None)


def main() -> None:
    load_env()
    token = require("DISCORD_BOT_TOKEN")

    try:
        import discord
    except ImportError:
        print("[msp_bot] discord.py is not installed.\n"
              "          venv/Scripts/python.exe -m pip install -U discord.py",
              file=sys.stderr)
        sys.exit(1)

    if "--discover" in sys.argv:
        discover(token, discord)
        return

    owner_id = require_id("DISCORD_OWNER_ID")
    channel_id = require_id("DISCORD_BOT_CHANNEL_ID")

    intents = discord.Intents.default()
    # Without this the bot receives empty message bodies and looks broken.
    # It must ALSO be switched on in the Developer Portal; the library flag
    # alone is not enough.
    intents.message_content = True

    client = discord.Client(intents=intents)
    busy = asyncio.Lock()

    @client.event
    async def on_ready() -> None:
        print(f"[msp_bot] connected as {client.user}", flush=True)
        print(f"[msp_bot] taking orders from user {owner_id} "
              f"in channel {channel_id} only", flush=True)
        channel = client.get_channel(channel_id)
        if channel is not None:
            await channel.send("MultiSportPredict is up. `!help` for commands.")

    @client.event
    async def on_message(message: Any) -> None:
        # Both locks. Silence on failure is deliberate -- see the docstring.
        if message.author.id != owner_id or message.channel.id != channel_id:
            return
        content = (message.content or "").strip()
        if not content.startswith("!"):
            return
        if len(content) > MAX_INPUT:
            await message.channel.send(f"Too long (max {MAX_INPUT} characters).")
            return

        parts = content[1:].split()
        if not parts:
            return
        name, args = parts[0].lower(), parts[1:]

        handler = COMMANDS.get(name)
        if handler is None:
            await message.channel.send(
                f"No command `!{name}`. Try `!help`.")
            return

        if busy.locked():
            await message.channel.send("Still working on the last one. Hold on.")
            return

        async with busy:
            await message.add_reaction("\N{HOURGLASS}")
            try:
                # The model can take a minute. Running it on the event loop
                # would stall the heartbeat and Discord would drop the bot.
                output = await asyncio.to_thread(handler, args)
            except BadCommand as exc:
                output = str(exc)
            except Exception as exc:                    # noqa: BLE001
                traceback.print_exc()
                output = f"{type(exc).__name__}: {exc}"
            for block in chunks(output):
                await message.channel.send(block)

    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
