# Running the model from your iPhone

Discord bot. You type in a channel, your PC does the work, the answer comes
back in the same channel. No SSH, no VPN, no port forwarding, nothing listening
on your machine.

Ten minutes, most of it clicking.

---

## 1. Create the bot

Go to **https://discord.com/developers/applications** → **New Application**.
Name it whatever you like. **Create**.

## 2. Get the token

Left sidebar → **Bot** → **Reset Token** → **Yes, do it** → **Copy**.

Paste it somewhere for a second. You cannot view it again — only reset it.

This token *is* the bot. Anyone holding it controls it. It goes in `.env`,
which is already in your `.gitignore` and is not tracked by git — I checked.
Never paste it in a chat, a screenshot, or a commit.

## 3. Turn on Message Content Intent

Same **Bot** page → scroll to **Privileged Gateway Intents** →
switch **MESSAGE CONTENT INTENT** on → **Save Changes**.

**Do not skip this.** Without it the bot connects fine, looks healthy, and
receives every message with the text stripped out. It will appear to ignore
you and there is no error anywhere explaining why.

## 4. Invite it to your server

Left sidebar → **OAuth2** → **URL Generator**.

- **Scopes:** tick `bot`
- **Bot Permissions:** tick `Send Messages`, `Read Message History`,
  `Add Reactions`

Copy the URL at the bottom, open it in a browser, pick your server, **Authorize**.

Give it nothing else. It does not need to manage the server, and a token that
leaks can only do what the bot was granted.

## 5. Get your two IDs

In Discord: **Settings → Advanced → Developer Mode → ON**.

- Right-click **your own name** in the member list → **Copy User ID**
- Right-click **the channel** you want to use → **Copy Channel ID**

Use a private channel. Anyone who can read it will see your picks.

## 6. Put the three values in `.env`

Open `C:\MultiSportPredict\.env` and add:

```
DISCORD_BOT_TOKEN=paste_the_token_here
DISCORD_OWNER_ID=paste_your_user_id
DISCORD_BOT_CHANNEL_ID=paste_the_channel_id
```

No quotes, no spaces around the `=`.

## 7. Install the library

```bash
venv/Scripts/python.exe -m pip install -U discord.py
```

## 8. Start it

Double-click **`start_bot.bat`**.

You should see:

```
[msp_bot] connected as YourBot#1234
[msp_bot] taking orders from user 123... in channel 456... only
```

and the bot posts `MultiSportPredict is up.` in your channel.

**Leave that window open.** Closing it stops the bot. It restarts itself on a
crash or a dropped connection, but not if you close the window.

---

## Using it from the phone

Open Discord on your iPhone, go to that channel, type:

```
!help
```

The commands:

```
!tennis Carlos Alcaraz vs Taylor Fritz          run a match
!tennis Alcaraz vs Fritz -450 +340              with the market price
!mlb Milwaukee Brewers vs Texas Rangers
!slate slate_mls.json

!push 1 3          push those soccer lines to Discord
!tpush 1           push those tennis lines

!players alcaraz   search tennis players
!teams MLS         teams in a league
!team Portland Timbers

!check soccer      data guard: stale or thin
!record baseball   win rate and units
!pending 3         what still needs a final score
```

An hourglass reaction means it is working. A model run takes up to a minute.

**Nothing reaches your public feed until you `!push` it.** Running a match
predicts it and shows you the table privately. Pushing is a separate word.

---

## How it is locked down

You are running code on your PC from a chat app. That deserves saying out loud.

**Two locks, both required.** A message must come from your user ID *and*
arrive in your channel ID. Failing either, the bot does nothing and says
nothing. The silence is deliberate: replying "you are not authorised" confirms
to a stranger that the bot is real, listening, and worth another try.

**No shell.** Commands are built as argument lists and handed to `subprocess`
directly — there is no command string for a `;` or `&&` to escape from.
`!slate slate_mls.json; del *.*` is a filename that does not exist, and that is
all it can ever be.

**Allowlists, not blocklists.** Every argument is checked against what it is
allowed to be rather than scanned for what it is not: numbers must parse as
integers in range, slate names must match a pattern *and* already exist on
disk, sports must be in a fixed set. A blocklist is a guess about what an
attack looks like. An allowlist is a statement about what is legal, and it is
still right about attacks nobody thought of.

**One job at a time.** A held lock means mashing a command queues it instead of
forking twenty Python processes.

**Caps on both ends.** Input is capped at 300 characters; output is truncated
to four messages.

Verified before shipping — each of these was rejected:

```
../../../etc/passwd          not a slate filename
slate_mls.json; del *.*      not a slate filename
1;rm                         not a line number
500                          out of range
curling                      not a sport
```

---

## What this does not solve

**Your PC has to be on and awake.** Check
**Settings → System → Power → Screen and sleep** and set sleep to Never, or the
bot dies every time the machine naps.

**The bot window has to stay open.** If you want it surviving a reboot, that is
a Windows scheduled task — worth doing once this has earned its keep.

**It is not a web app.** No charts, no tapping through a slate. It is a command
line that happens to live in Discord. That is the trade for having it tonight.

---

## Why not SSH

You said you wanted Termius for the learning, and that is still worth doing —
as its own project, not against a deadline.

The difference matters: this bot opens an **outbound** connection to Discord and
keeps it. Nothing on your PC listens, no port is forwarded, your home IP is
never published, and it works from anywhere with signal on day one.

SSH means a **listening service on a Windows box reachable from the internet**.
Done properly — keys only, password auth off, non-standard port, fail2ban or the
Windows equivalent, ideally Tailscale so it is never actually public — it is
fine and you will learn a lot. Done at 11pm to hit a deadline, it is the single
most-scanned port on the internet answering on your home connection.

Do it deliberately, with time to read what each step does. The bot covers you
until then.

---

## If it does not work

**Bot appears offline** — the token is wrong or `start_bot.bat` is not running.
Look at the window.

**Bot is online but ignores you** — this is almost always Message Content Intent
(step 3). Second most likely: the user ID or channel ID is wrong. The window
prints both on startup; compare them against Discord.

**"discord.py is not installed"** — step 7.

**Bot replies to `!help` but commands fail** — that is your model, not the bot.
The error text is the script's own. Run the same thing at the PC to see it in
full.
