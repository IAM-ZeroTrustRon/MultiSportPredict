# Odds collection operational status — October 25, 2026

No scheduler is activated. No standing paid API allowance has been approved.

## Current supported paths

NHL and NBA/WNBA/NCAAB/NCAAW/NCAAF score runners archive their priced forecast
markets. Prediction payloads now retain run ID when available, official fixture
ID, provider event ID, bookmaker, period, settlement scope, selections, original
American prices, provider update time and observed time. Missing kickoff fails
capture. Unknown/manual bookmaker identity cannot establish comparable CLV.

The archive is the existing odds_snapshots table in multisport_history.db.
No additional production database is used. Existing immutable rows are preserved.
Prediction-time collection reuses prices already fetched; it makes no new odds call.
EuroLeague lacks verified kickoff/provider metadata in its current payload, so
capture can be refused. Soccer, MLB/KBO, NFL, tennis and TT are not integrated into
this score-runner capture/collector path. Do not claim all-sport CLV coverage.

## One manual collection

```bash
venv/Scripts/python.exe -u closing_collector.py --league NHL
venv/Scripts/python.exe -u clv.py --sport nhl --json
```

The collector first looks for tracked prediction snapshots inside a 30-to-1-minute
window. With no eligible tracked prediction it makes zero paid odds calls. It then
fetches fresh official fixture/status information, requiring the original official
ID, home/away and kickoff to agree. Changed kickoff, postponement or started games
are refused for review; no old snapshot is rewritten. Only then may it request
one league odds response (h2h/spreads/totals, region us). It captures only tracked
provider event IDs, original bookmaker and market. The provider response may cover
a league, but unrelated events/markets are never written.

Default quote maximum age: 5 minutes. Observed and provider times must be strictly
before kickoff; future publication times and explicit in-play flags are refused.
Use --event-id to target one tracked provider ID. --dry-run prevents snapshot
writes but can still spend one odds request if the tracked preflight succeeds.
--events-file plus --fixtures-file permits offline replay with no paid request.

Repeated collection of the same bookmaker publication is idempotent, including
concurrent inserts. A later genuine provider update creates a separate immutable
observation. Both snapshot UPDATE and DELETE remain prohibited by existing triggers.

## What the report means

The database category 'closing' is retained for compatibility. It means a candidate
last-observed prematch reference, NOT proof of the sportsbook's final closing quote.
The report shows minutes before kickoff. It compares only matching sport/league,
provider event, oriented teams, bookmaker, market, period and settlement scope.
A changed kickoff requires separate verified reschedule linkage; it is not inferred.
Each saved run/market observation is kept; these are correlated observations,
not independent bets or an accuracy/ROI report.

The latest eligible observation is the reference. An older same-line capture is
not substituted to conceal later line movement. Different lines produce line
movement only. For matching lines:
- Raw price CLV = prediction decimal / reference decimal - 1.
- Fair-price CLV = prediction decimal * same-bookmaker de-vigged reference
  probability - 1, where a complete binary fair probability is supported.
- Fair-probability percentage-point movement is a separate diagnostic.
No consensus market or model-quality conclusion is claimed. Integer spread/total
push markets retain raw price comparison but no binary fair probability.

## Budget and scheduling decision

One request is not one credit. The live collection report saves only the allowlisted
x-requests-last, x-requests-used and x-requests-remaining response headers. Missing
headers mean measured credit usage is unavailable. Three markets in one region
commonly imply three credits, but use actual account/provider headers rather than
advertised plan assumptions. Do not buy or change any subscription.

Next: one bounded manual live test with a real existing/new pregame prediction.
Only after that evidence is reviewed should a timer be proposed. A timer must gate
locally on tracked fixtures, use a bounded per-day budget and stop on rate-limit or
quota failure; no daemon, cron, Windows task or Codex automation is installed here.
