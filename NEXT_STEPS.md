# Where things stand — 2026-08-28

Pick up here. Commands live in `COMMANDS.md`.

---

## Working right now

| Data | Status |
|---|---|
| MLB teams | 30, with home/away splits + last-10 form |
| MLB probable starters | today + tomorrow, with ERA/K9 |
| KBO teams | 10 |
| EuroLeague | 20 teams |
| Liga MX | 18 teams |
| NFL 2025 | 32 teams (the prior season, for early-season weeks) |

Predictions push to Discord. Soccer embeds now match the baseball layout.

## Not working, and why

| Source | Blocked by |
|---|---|
| FBref (soccer xG) | Cloudflare 403 |
| FanGraphs (MLB player props) | Cloudflare 403 |
| RealGM (KBL, NZ NBL) | Cloudflare 403 |
| ESPN `site.api.espn.com` | Akamai 403 |
| GitHub raw files | 404 — the Sackmann tennis repo is gone |

Not fixable with headers. These need different sources, not retries.

**Already-saved pages that would let those be rebuilt offline**, in `data/cache/probe/`:
`kbl_landing__*.html` (KBL stats, 300KB), `nznbl_landing__*.html` (NZ NBL standings and stats),
`tennisabstract.html` (publishes surface-split Elo directly — better than computing it).

---

## Next, in order

**1. Grade the games from Aug 28.** Three MLB, one Liga MX. Nothing has ever been graded — 113 logged, 0 scored.

```
.venv/Scripts/python.exe grade_predictions.py --auto --report
```

**2. Clean the duplicate predictions.** Aug 28 logged each MLB game twice and León–Atlante three times. Duplicates will distort the win rate once grading starts.

**3. NFL Day 2 — the predictor.** `models/nfl_predictor.py`. Everything for it is in `NFL_ENGINE_PLAN.md`: points model, margin→win-probability at 13.5 SD, home field 1.8, and the key-number rule around 3 and 7. Data is already ingested.

**4. Phone access — one step left.** SSH server is on and working. Blocked because Python came from the Microsoft Store, so it's locked to the RonRi profile and the `msp` account can't reach it.

Simple fix: `net user RonRi *` in admin PowerShell to set a password you know, then connect Termius as `RonRi` instead of `msp`. Host `172.20.20.20`, port 22.
Proper fix: reinstall Python with "install for all users", rebuild the venv, keep using the non-admin `msp` account.
Away from home also needs Tailscale on both devices.

Once connected: `cd /c/MultiSportPredict && ./msp` for the menu.

---

## Two standing cautions

**Market lines are placeholders.** MLB defaults to 8.5, soccer to 2.5. An edge measured against an invented line is the gap between the guess and the book, not a real edge. Pass `--odds` or edit the constants.

**Liga MX and Eerste Divisie xG is estimated from goals** (`data_tier: 2`) — no reachable source publishes real xG. Weaker evidence than the number alone suggests.
