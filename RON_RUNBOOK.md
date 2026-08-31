# Ron's runbook — MultiSportPredict

Everything you actually type. Keep this open instead of scrolling chat.

**Terminal: Git Bash. Folder: `C:\MultiSportPredict`.**

```bash
cd /c/MultiSportPredict
```

---

## The one rule

Every command starts with **`venv/Scripts/python.exe`**.

Never plain `python`. Never `.venv`. Two different agents have now told you the
venv is broken — it isn't, and both times "the fix" was the interpreter that
hangs your terminal for two minutes. If a command seems to freeze, that is why.

---

## Tonight, in order

### 1. Build the tennis data (once, ~2-5 min)

```bash
venv/Scripts/python.exe ingest_tennis.py
```

Nothing tennis is real until this finishes. It should end with a match count and
a date range.

### 2. Run the six ATP matches

```bash
venv/Scripts/python.exe run_tennis.py --tournament "US Open" --round R1 --surface hard \
  --match "Coleman Wong vs Tommy Paul" \
  --match "Jiri Lehecka vs Pablo Carreno Busta" \
  --match "Miomir Kecmanovic vs Denis Shapovalov" \
  --match "Luca Van Assche vs Cameron Norrie" \
  --match "Martin Landaluce vs Jacob Fearnley" \
  --match "Daniil Medvedev vs Hugo Gaston"
```

Nothing goes to Discord yet. You get a table. Read the EDGE column.

### 3. Push the ones you like

```bash
venv/Scripts/python.exe run_tennis.py --push 1 2 3 4 5 6
```

Drop numbers you don't want: `--push 2 5`.

### 4. Run the five KBO games

```bash
venv/Scripts/python.exe run_mlb.py --league KBO \
  --match "Samsung Lions vs KT Wiz" \
  --match "Lotte Giants vs LG Twins" \
  --match "Hanwha Eagles vs NC Dinos" \
  --match "KIA Tigers vs SSG Landers" \
  --match "Doosan Bears vs Kiwoom Heroes"
```

This one pushes as it runs. Add `--no-discord` if you want to look first.

Four of the five have rain warnings. Rained-out games just stay ungraded.

---

## Where your picks go

Right now: **your bot channel only. Webhooks are off.**

That's this line in `C:\MultiSportPredict\.env`:

```
DISCORD_PUSH_TARGET=bot
```

### To change it permanently

Edit that one line:

| Set it to | What happens |
|---|---|
| `bot` | bot channel only (what you have now) |
| `webhooks` | your old webhooks only, bot channel off |
| `all` | both |

Save. Takes effect on the next command — no restart.

### To change it for one command only

Put it in front of the command. Don't edit the file:

```bash
DISCORD_PUSH_TARGET=all venv/Scripts/python.exe run_tennis.py --push 1
```

```bash
DISCORD_PUSH_TARGET=webhooks venv/Scripts/python.exe run_mlb.py --league KBO --match "Doosan Bears vs Kiwoom Heroes"
```

The shell always beats the file, so this is safe — it changes nothing permanent.

### To add more webhooks

One line in `.env`, space or comma separated:

```
DISCORD_WEBHOOK_URLS=https://discord.com/api/webhooks/aaa https://discord.com/api/webhooks/bbb
```

Already merged and de-duplicated with the two you have. No code change needed.

---

## Phone bot

```bash
venv/Scripts/python.exe -m pip install -U discord.py     # once
```

Then double-click `start_bot.bat` and leave the window open.

From Discord on your phone, in your channel:

```
!help
!tennis Carlos Alcaraz vs Taylor Fritz -450 +340
!slate slate_mls.json
!push 1
!record tennis
!check soccer
```

Your PC has to be awake: **Settings → System → Power → Screen and sleep → Never.**

---

## Daily rhythm

```bash
venv/Scripts/python.exe data_guard.py                          # is my data stale?
venv/Scripts/python.exe grade_predictions.py --auto --report    # score yesterday
venv/Scripts/python.exe grade_predictions.py --pending --days 3 # what needs scores
./msp status                                                    # what's on disk
```

---

## When something breaks

**Terminal hangs and never comes back.**
You used plain `python`. Ctrl+C, retry with `venv/Scripts/python.exe`.

**"No module named 'scipy'" / "'discord'" / "'bs4'".**
Same cause — wrong interpreter. Those packages are in `venv`, not `.venv`.

**A name won't resolve.**
Find the store's spelling; don't guess:

```bash
venv/Scripts/python.exe run_tennis.py --list "fritz"
venv/Scripts/python.exe run_mlb.py --league KBO --list-teams
```

**"STALE DATA — nothing was run".**
Working as designed. The data is too old or too thin. Re-ingest that sport.

**"[SKIP] ... NOTHING WAS SENT".**
You already pushed that exact prediction in the last 6 hours. Not an error.

**Discord got nothing and no error.**
Check `DISCORD_PUSH_TARGET`. If it says `bot`, look in the bot channel, not your
old webhook channel.

---

## Two things to stay skeptical about

**Predictions can be produced for games that don't exist.** On Aug 29 the model
output nine — four Serie A, five KBO — with confidence scores and edges, for
matchups never scheduled. Nothing in the pipeline checks a fixture against a real
schedule yet. Until it does, glance at the matchups before you push.

**Hand-written stats look identical to real ones.** `data/tennis/players.json`
currently holds six players with invented Elo ratings. Running the ingest in
step 1 replaces them with numbers derived from actual results. If a file appears
with plausible stats and you didn't run an ingest to create it, don't trust it.
