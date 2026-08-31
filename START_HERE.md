# Do these 4 steps, in order

Nothing else. About 10 minutes, most of it waiting.

---

## Step 1 — Stop the bot

Find the black terminal window on your PC that says something like:

```
[msp_bot] connected as YourBot#1234
[msp_bot] taking orders from user 1234... in channel 5678... only
```

That is the bot. It was started by `start_bot.bat`.

**Click on that window, then press `Ctrl+C` twice.**

Press it once, wait a second, press it again. Twice is required — the launcher
is written to restart the bot automatically if it stops, and the second Ctrl+C
is what tells the launcher itself to quit.

Then **close the window** with the X.

Your bot now shows offline in Discord. That is correct.

> **Can't find the window?** Press `Ctrl+Shift+Esc` to open Task Manager. Look
> for `Python` or `Windows Command Processor`. Right-click → End task. Any of
> them; you can always start it again.

---

## Step 2 — Build the tennis data

Open **Git Bash**. Type these two lines, pressing Enter after each:

```bash
cd /c/MultiSportPredict
```

```bash
venv/Scripts/python.exe ingest_tennis.py
```

**Wait.** It downloads four files (ATP and WTA, 2025 and 2026). Two to five
minutes. Text will scroll.

**You are done when you see something like this at the bottom:**

```
  14832 matches   1104 players   2025-01-01 .. 2026-08-29
  by surface: clay 4210, grass 1180, hard 9442

Wrote data/tennis/matches.csv
Wrote data/tennis/players.json
```

Those exact numbers will be different. What matters is that it says
**`Wrote data/tennis/matches.csv`**.

**If it says `Nothing was ingested`** — stop here and tell me. Nothing was
broken; it just could not download, and your old files are untouched.

---

## Step 3 — Start the bot again

Open the `C:\MultiSportPredict` folder in File Explorer.

**Double-click `start_bot.bat`.**

A black window opens. Wait for:

```
[msp_bot] connected as YourBot#1234
```

and the bot posts `MultiSportPredict is up.` in your Discord channel.

**Leave this window open.** Closing it stops the bot. You can minimize it.

---

## Step 4 — Test it from your phone

Open Discord on your phone, go to your bot channel, and send these one at a
time:

**Test 1 — is the new command list loaded?**

```
!help
```

You should see `!kbo` in the list. If `!kbo` is missing, the bot did not
actually restart — go back to Step 1.

**Test 2 — is the tennis data real?**

```
!players fritz
```

You should get a player with a win-loss record and a ranking. If it says
"No tennis store yet", Step 2 did not finish.

**Test 3 — run a real match**

```
!tennis Coleman Wong vs Tommy Paul
```

An hourglass appears while it works. Up to a minute.

If you get `NO MATCH HISTORY -- nothing was run`, Step 2 did not finish.

**Test 4 — run a KBO game**

```
!kbo Doosan Bears vs Kiwoom Heroes
```

---

## Where things show up now

| What | Where it appears |
|---|---|
| Your typed command | your bot channel |
| The bot's answer / review table | your bot channel |
| A pushed prediction | **your webhook channel** |

That is the setting you asked for: run everything in the bot, picks go to the
webhook.

Running a match does **not** push it. To push:

```
!push 1 3          soccer lines from the last slate
!tpush 1           tennis lines from the last run
```

---

## To change where picks go later

Edit one line in `C:\MultiSportPredict\.env`:

```
DISCORD_PUSH_TARGET=webhooks     <- current: picks go to your webhooks
DISCORD_PUSH_TARGET=bot          <- picks go to the bot channel instead
DISCORD_PUSH_TARGET=all          <- both
```

Save. No restart needed for this — it is read fresh on every command.

---

## The full ATP and KBO cards

Once Step 4 passes, run these at the PC in Git Bash — six matches at once is
easier to read there than on a phone.

```bash
venv/Scripts/python.exe run_tennis.py --tournament "US Open" --round R1 --surface hard \
  --match "Coleman Wong vs Tommy Paul" \
  --match "Jiri Lehecka vs Pablo Carreno Busta" \
  --match "Miomir Kecmanovic vs Denis Shapovalov" \
  --match "Luca Van Assche vs Cameron Norrie" \
  --match "Martin Landaluce vs Jacob Fearnley" \
  --match "Daniil Medvedev vs Hugo Gaston"
```

Read the table, then push the ones you want:

```bash
venv/Scripts/python.exe run_tennis.py --push 1 2 3 4 5 6
```

KBO, review first:

```bash
venv/Scripts/python.exe run_mlb.py --league KBO --no-discord \
  --match "Samsung Lions vs KT Wiz" \
  --match "Lotte Giants vs LG Twins" \
  --match "Hanwha Eagles vs NC Dinos" \
  --match "KIA Tigers vs SSG Landers" \
  --match "Doosan Bears vs Kiwoom Heroes"
```

To push them, run that same command again **without** `--no-discord`.
