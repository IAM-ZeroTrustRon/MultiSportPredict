# MultiSportPredict — Handoff

**For:** whoever picks this up next (Gemini, another assistant, or future me)
**Written:** 2026-08-29, end of day
**Repo:** https://github.com/IAM-ZeroTrustRon/MultiSportPredict
**Project root:** `C:\MultiSportPredict` (Windows 11, machine name GameChanger, user RonRi)

Read `COMMANDS.md` for every command. `DAILY_INGESTION.md`, `RESULTS_TRACKING.md`
and `NFL_ENGINE_PLAN.md` cover their areas in depth.

---

## What this project is

A multi-sport betting prediction model. It scrapes team stats, runs matchups
through per-sport predictors, pushes recommendations to Discord, and grades them
against real results to build a win-rate record.

Sports: soccer, baseball (MLB + KBO), basketball (EuroLeague, KBL, NZ NBL),
tennis. NFL is being added.

---

## Current state — verified 2026-08-29

### Data on disk

| Store | Contents |
|---|---|
| `data/baseball_stats.json` | 40 teams — 30 MLB (with home/away splits + last-10 form), 10 KBO |
| `data/soccer_stats.json` | 81 teams — Premier League 44, Eredivisie 19, Liga MX 18 |
| `data/nfl_stats.json` | 32 teams, 2025 season (the prior season, deliberately) |
| `data/euroleague_stats.json` | 20 teams |
| `data/mlb_probables.json` | today's and tomorrow's starters with ERA/K9 |

### Predictions

**122 logged, 14 graded.** Graded so far are all baseball: 10-4, +9.09 units.
Ungraded: 69 soccer, 18 mlb, 12 baseball, 6 basketball, 3 tennis.

### Git

Last commit `4d51e1e`. **21 files uncommitted** — commit these.

---

## Data sources: what works and what is walled off

This matters more than anything else here. Four sources are blocked, and
retrying them with different headers will not help.

| Source | Status |
|---|---|
| statsapi.mlb.com | **works** — official MLB API, no key |
| mykbostats.com | **works** — KBO team splits |
| football-data.co.uk | **works** — soccer match results as CSV |
| api.the-odds-api.com | **works** — key in `.env`, `/events` is free |
| site.web.api.espn.com | **works** — NFL standings |
| sports.core.api.espn.com | **works** — NFL per-team statistics |
| FBref | **403 Cloudflare** |
| FanGraphs | **403 Cloudflare** (breaks pybaseball → MLB player props) |
| RealGM | **403 Cloudflare** (breaks KBL, NZ NBL) |
| ESPN `site.api.espn.com` | **403 Akamai** — note this is a *different host* from the two that work |
| Pro-Football-Reference | **403** — do not build against it |
| GitHub raw / jsDelivr | **404** — the Sackmann tennis repo is gone from public view |

A diagnostic confirmed no proxy, correct DNS, and genuine TLS certificates on
this machine. These are site-side blocks, not a local network problem.

**Consequence for soccer:** no reachable source publishes expected goals. All
soccer xG in the store is **estimated from goals** and tagged `data_tier: 2`.
Treat those edges as weaker evidence than the number alone suggests.

**Unfinished leads:** `data/cache/probe/` holds already-downloaded pages that
would let KBL and NZ NBL be rebuilt offline (`kbl_landing__*.html`,
`nznbl_landing__*.html`), plus `tennisabstract.html` — Tennis Abstract publishes
surface-split Elo directly, which is better than computing it from match history.

---

## THE OPEN ITEM: phone access over SSH

**Ron is confused about where this stands and wants to revisit it. Here is the
factual state — do not assume a decision was made, because it was not.**

### Confirmed working

- OpenSSH Server installed on Windows and running (`sshd`, startup Automatic)
- Firewall rule for port 22 exists
- Default SSH shell set to Git Bash via registry — **this succeeded**
- PC's LAN address: **172.20.20.20** (Wi-Fi adapter; ignore 192.168.56.1 which is
  VirtualBox and 172.20.208.1 which is WSL)
- A local Windows account **`msp`** was created, added to Users, and granted
  Modify on `C:\MultiSportPredict`
- `msp` **can** SSH in and gets a Git Bash prompt. `./msp status` runs.

### The blocker

`msp` **cannot run Python.** Python was installed from the Microsoft Store, so
it lives at
`C:\Users\RonRi\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_...`
with ACLs that only RonRi can read. The venv points at it. So `msp` sees the
project folder but cannot execute anything in it.

### Also true

Ron **does not know the RonRi Windows password**, so SSHing as RonRi fails at
authentication. The SSH handshake itself succeeds — it is purely the credential.

### Two ways forward, neither chosen

**A. Reset the RonRi password and SSH as RonRi.**
`net user RonRi *` in admin PowerShell. Two minutes. Costs: SSH runs as an admin
account, and resetting a local password can invalidate Windows Credential
Manager — including the saved GitHub credentials, which would need re-entering.

**B. Install Python for all users and rebuild the venv.** ~20 minutes. Keeps
`msp` as a non-admin account that cannot touch anything outside the project.
Permanently removes a class of problem that will otherwise recur with scheduled
tasks and services.

**Away from home, either option additionally needs Tailscale** on the PC and the
iPhone. Currently this only works on the home Wi-Fi. Do not suggest forwarding
port 22 on the router.

### A trap to avoid

An earlier attempt at option B ran `Rename-Item venv venv_store_backup` but the
rebuild step never ran, which left the project with **no venv at all** and every
script failing with `No such file or directory`. Recovered with
`mv venv_store_backup venv`. If option B is attempted, do the rename and the
rebuild together, and confirm an all-users Python exists **first**:

```powershell
where.exe python
Test-Path "C:\Program Files\Python313\python.exe"
```

A `.venv` folder (with a dot) also exists — a stray empty environment from that
attempt. Harmless, safe to delete, not used by anything.

---

## Working notes on Ron's setup

- **Shells:** Git Bash (MINGW64) is the daily driver. Forward slashes,
  `venv/Scripts/python.exe`. PowerShell needs backslashes. Only `schtasks`
  genuinely requires Command Prompt. Slash direction has caused repeated errors —
  always state which shell a command is for.
- **Always use `venv/Scripts/python.exe`**, never bare `python` — the packages
  live in the venv.
- Ron has asked more than once for simpler, less technical explanations. Long
  multi-step terminal sequences have caused confusion. Prefer one command at a
  time with a stated expected outcome.
- VirtualBox, WSL, and Ubuntu are installed. **WSL cannot use the Windows venv** —
  do not suggest running project scripts from WSL.

---

## Immediate next steps

1. **Commit the 21 uncommitted files.** Everything from today is unpushed.
2. **Grade the outstanding predictions.** 108 still ungraded.
   `venv/Scripts/python.exe grade_predictions.py --auto --report`
   MLB grades automatically; other sports need the `--pending` CSV route.
3. **Clean duplicate predictions.** Aug 28 logged several matchups two and three
   times. Duplicates will distort the win rate.
4. **Decide the SSH question** (section above).
5. **NFL Day 2 — the predictor.** `models/nfl_predictor.py`. Data is already
   ingested; the design is in `NFL_ENGINE_PLAN.md`: points model, margin to win
   probability at 13.5 SD, home field 1.8 points, suppress edges under ~1.5
   points near the key numbers 3 and 7.

---

## Standing cautions

**Market lines default to placeholders** (MLB 8.5, soccer 2.5). An edge measured
against an invented line is the gap between the guess and the book, not a real
edge. Use `--odds` or pass the real number.

**Spread markets are deliberately ungraded.** The stored `model_value` does not
record which side the number belongs to. The fix belongs where predictions are
written, not in the grader.

**Sample size is the real constraint.** 14 graded bets tells you nothing yet.
Break-even at -110 is 52.4%; under ~30 settled bets the number moves several
points on a single result.

**The recurring bug class in this codebase:** predictors silently defaulting to
league averages when a lookup misses, so every matchup looks identical. It has
been found and fixed three times — soccer, then MLB, then KBO. If a new sport is
added, make the lookup miss raise or warn loudly. Never let it fall through.
