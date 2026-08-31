# MCP setup — MultiSportPredict

The server is already written and tested: `C:\MultiSportPredict\mcp_server.py`.
Nothing to install. All that's left is telling each client where it lives.

---

## First: the form in the Cline screenshot is the wrong one

"Add a remote MCP server — Server Name / Server URL / Transport Type" only adds
servers that live on the internet at an `https://` address. Yours runs on your
own machine over stdin/stdout. That form has no way to express it. **Cancel it.**

Local servers get added by editing a JSON file. Both clients use the same shape.

---

## Claude Desktop

1. Open the file:

   Press `Win+R`, paste this, press Enter:

   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

   If Windows asks what to open it with, pick Notepad or VS Code.
   If the file doesn't exist, create it in that folder with exactly the content below.

2. Paste this. If the file already has other servers, add only the
   `"multisportpredict": { ... }` block inside the existing `"mcpServers"`.

```json
{
  "mcpServers": {
    "multisportpredict": {
      "command": "C:\\MultiSportPredict\\venv\\Scripts\\python.exe",
      "args": ["C:\\MultiSportPredict\\mcp_server.py"]
    }
  }
}
```

3. **Fully quit Claude Desktop** — right-click the tray icon, Quit. Closing the
   window isn't enough; it keeps running and won't reload the config.

4. Reopen it. The tools appear under the slider icon in the chat box.

---

## Cline

1. In the Cline panel, click the **MCP** tab, then the gear/settings icon, and
   choose **Configure MCP Servers**. That opens `cline_mcp_settings.json` in the
   editor. (Don't hand-type the path — the button always opens the right file.)

2. Paste the same block, with two extra Cline-specific keys:

```json
{
  "mcpServers": {
    "multisportpredict": {
      "command": "C:\\MultiSportPredict\\venv\\Scripts\\python.exe",
      "args": ["C:\\MultiSportPredict\\mcp_server.py"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

3. Save. Cline reloads on save — no restart.

`autoApprove` is deliberately empty. Leave it that way. Putting `push_to_discord`
in it means an agent can post to your feed without asking you first, which is the
one action here that other people see.

---

## The 11 tools

| Tool | What it does |
|---|---|
| `list_teams` | What's seeded in a store, by league, with games played |
| `team_stats` | One team's full record — season, tier, source |
| `check_data` | Runs `data_guard.py`. Wrong-season, thin-sample, stale |
| `run_slate` | Runs a slate JSON, prints the de-vigged comparison table |
| `run_mlb` | Runs MLB matchups |
| `pending_results` | Ungraded predictions; writes `pending_results.csv` |
| `grade_results` | Grades from the filled CSV, prints the record |
| `record` | Win rate and units, bets separated from passes |
| `ingest` | Runs one daily adapter |
| `ingest_soccer` | Refreshes soccer from football-data.co.uk |
| `push_to_discord` | Pushes reviewed picks by line number |

---

## Try it

In either client, ask in plain language:

- "What MLS teams are in the store?"
- "Check my data for stale records"
- "Run slate_mls.json"
- "What's my record on soccer?"

---

## Two design decisions worth knowing

**No dependencies.** The official `mcp` Python SDK would work, but it's a pip
install that has to succeed before the server can start at all — and a server
that can't start tells the client nothing except "failed". The stdio transport is
one JSON object per line. That's small enough to own, and owning it means the
file runs under any Python 3.9+ with an empty environment.

**Tools shell out instead of importing.** Every tool runs the existing script as
a subprocess. If `mcp_server.py` imported `predict_match`, then a missing scipy
or one syntax error in a runner would kill the server at startup and the client
would show zero tools. As a subprocess, a broken runner is one failed tool call
with its stderr attached, and the other ten keep working.

---

## If it doesn't show up

Run the server by hand first — this isolates the server from the client:

```bash
venv/Scripts/python.exe mcp_server.py --selftest
```

Expect `PASSED (0 failure(s), 11 tools registered)`.

If that passes and the client still shows nothing, the problem is the config
file, not the server. Check in this order:

1. **Is the JSON valid?** A trailing comma or a single backslash breaks it
   silently. Paths need **double** backslashes: `C:\\MultiSportPredict\\...`
2. **Did Claude Desktop actually quit?** Tray icon → Quit, not the window X.
3. **Is the python path right?** `C:\MultiSportPredict\venv\Scripts\python.exe`
   must exist. If you rebuilt the venv, it does — but confirm.

Claude Desktop's MCP log is at `%APPDATA%\Claude\logs\`. Cline shows server
errors in its MCP tab.

---

## One thing this does not fix

The server runs on your PC. It's reachable from Claude Desktop and Cline **on
that PC only** — not from your phone. Running slates from your phone still needs
either the SSH/Termius route or the web app. This is a step toward the web app,
not a replacement for it: the tool layer you'd expose over HTTP is now written.
