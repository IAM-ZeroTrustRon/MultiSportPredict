# Working across tools/environments (Cline, Claude Code web, local shells)

This repo gets worked on from at least two different kinds of environment,
and they are not interchangeable. Read this before assuming another tool's
run applies to yours, or that your changes are automatically visible to it.

## The split: who can reach the internet

- **Cline / any tool running on your own machine** has your normal network
  access. It's the only place that can run live ingestion: `auto_mlb_scraper.py`,
  `ingest_all_sports.py`, `universal_runner.py`'s live-odds path, or anything
  that hits `statsapi.mlb.com`, `api.the-odds-api.com`, ESPN, FBref, etc.
- **Claude Code on the web / cloud sessions** run in an isolated container
  whose outbound network is locked to an allowlist (package registries +
  Anthropic's own endpoints). It **cannot** reach any sports-data host —
  this is an org network policy, confirmed by direct testing, not a bug to
  route around. A cloud session asked to "run today's slate" needs the
  matchup/odds data handed to it (see below); it cannot fetch it itself.

If you manage this Claude Code environment's settings and want cloud
sessions to fetch live data directly, that's configured at the environment
level (network policy), not in code — see
https://code.claude.com/docs/en/claude-code-on-the-web.

## Data files never sync between environments — by design

`data/`, `external_data/`, `*.db` (including `multisport_history.db`) are
gitignored on purpose (see git history: "stop tracking the prediction
database"). Whichever tool ingests live data keeps it locally; it will
never appear in another session's checkout no matter how well branches are
synced. Don't try to "fix" this by un-gitignoring them — daily-refreshed
data doesn't belong in version control.

**To hand a specific day's matchups to another tool/session**, use a small
tracked snapshot file instead of a prose summary of what you ran:
- `slate_today.json` (repo root) is the existing pattern for this —
  `run_soccer_batch.py --slate slate_today.json` reads it, and it's
  plain, hand-editable JSON that's actually tracked in git.
- A session can only verify data it can read itself. A paragraph like
  "ingested 507 teams, stored 73 rows" is not independently checkable by
  another session and should not be treated as done until the actual file
  or DB is visible on disk (or in git) to whoever needs to act on it.

## Branch discipline

`main` is the convergence point. Claude Code web sessions are assigned a
fresh per-session branch (e.g. `claude/<slug>`) and push their commits
there; that branch should get merged (or PR'd) back into `main` promptly
rather than living indefinitely alongside other tools' independent local
branches. Before starting new work in *either* tool, pull `main` (or the
relevant shared branch) first — silent divergence between a local Cline
session and a cloud session's branch is the actual source of "confusion,"
not the tools themselves.

## Practical rule of thumb

- Live ingestion / anything hitting an external API → run it locally
  (Cline or your own shell), then commit+push the *code* changes (if any)
  and, if the data matters to a handoff, drop it into a tracked snapshot
  file like `slate_today.json`.
- Bug fixes, refactors, predictions against already-seeded or pasted data →
  fine in a cloud session.
- See `ARCHITECTURE.md` for which prediction modules are actually live vs.
  orphaned — check it before adding a new file so you don't rebuild
  something that already exists under a different name.
