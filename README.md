# MultiSportPredict

**A multi-sport handicapper built to evaluate the price of a bet.**

MultiSportPredict combines sport-specific analysis with market odds to look for line discrepancies and positive expected value. Its objective is disciplined long-term return on capital. Picking the most likely winner is only one input: a strong favorite can be poor value at its price, while an underdog can offer value despite being more likely to lose.

## How picks are approached

The workflow starts with the market: identify the exact fixture and priced market, account for the bookmaker margin where supported, and compare the available line with an estimated fair price. Sport-specific models add context such as scoring profiles, surface and player history, pitching, pace, form and scheduling when verified data is available. Confidence and data-quality checks help decide whether the result merits a recommendation or a pass.

Expected value describes the estimated payoff relative to the offered price over repeated comparable opportunities. It depends on the probability estimate being well calibrated and the quoted price being obtainable. An individual winning pick does not prove value; an individual loss does not disprove it. The project therefore aims to track the quality of pricing decisions, realised model returns and, where reliable opening/closing prices exist, closing-line value. Closing-line tracking remains a development area rather than a complete verified performance dataset.

This README describes the approach without publishing proprietary thresholds, weighting or selection recipes. Market coverage, price capture and model validation vary by sport. An unpriced simulation does not establish a betting edge, and a reported EV estimate is not a guaranteed return.

## Examples from the workflow

Historical screenshots show the market-comparison interface and an unpriced EuroLeague market remaining a pass. They illustrate project behavior, not independently verified accuracy or returns. Model-only/uncalibrated labels and older interface limitations remain visible.

![Historical tennis output comparing probabilities with market prices](docs/evidence/pricing/2026-10-09-tennis-market-comparison.png)

See the [categorized evidence gallery](docs/evidence/README.md) for dates, context, source-refresh and manual-input examples, and the limits of each capture.

## Current workflow

One interface handles refresh, match/slate runs, immutable saved reviews, grading and records. Sport-specific engines and their guards remain underneath it; the wrapper does not turn every runner into the same model. Table tennis uses the root workflow alongside the other sports.

**Git Bash, from the project folder:**

```bash
cd /c/MultiSportPredict
venv/Scripts/python.exe -u msp.py daily --all
venv/Scripts/python.exe -u msp.py record
venv/Scripts/python.exe -u msp.py pending
```

To run one verified fixture, edit the filled-in example values before execution:

```bash
venv/Scripts/python.exe -u msp.py run --sport kbo --match "KIA Tigers vs LG Twins" --date 2026-10-19
venv/Scripts/python.exe -u msp.py show --latest
```

The example illustrates syntax; it is not a claim that those teams play on that date. Runs save a review without sending Discord messages. Optional `msp.py push --latest` sends the latest successful saved snapshot after review; it does not rerun a model or place a wager.

See [all-sports commands](COMMANDS.md), [table-tennis commands](TABLE_TENNIS_COMMANDS.md), and the filled [mixed-sport slate example](slate_workflow.json). With Python 3.10+ and a project virtual environment, dependencies are listed in [requirements.txt](requirements.txt); table-tennis extras are in [requirements-table-tennis.txt](requirements-table-tennis.txt). The workflow deliberately uses the project virtual environment instead of silently selecting another Python installation.

## Historical record — transparent scope

As of October 19, 2026, the retained ordinary model record contains **181 wins, 195 losses and 3 pushes** (48.14% excluding pushes). The 238-selection recorded-price subset shows **+20.24 simulated units / +8.50% simulated ROI**, assuming one unit risked per selection. The remaining 141 grades lack confirmed recorded-price settlement and are excluded from that ROI.

**These are retained model records, not audited wagers.** Historical unresolved rows were removed after backup during a documented cleanup. That missing-outcome/selection bias prevents these figures from representing the complete original recommendation history. They should not be presented as verified profitability or a validated long-term edge. Different markets on the same game are correlated; BET and LEAN decisions are included, while PASS/INFO/VOID and duplicate reruns are excluded.

A fresh reporting period starts **October 20, 2026** with no graded selections. Settled history remains available with `msp.py record --all-time`. See the [dated performance snapshot and limitations](docs/PERFORMANCE_2026-10-19.md) for definitions, coverage and reproduction commands.

## Notable October improvements

- A shared command interface covers supported sport runners and mixed slates, with explicit saved-run and delivery records.
- NFL fixture dates use America/New_York, preserve event identity, and avoid previous-season fallback. Two-way NFL moneylines push on verified tied finals.
- KBO finals use a dedicated completed-score adapter instead of being routed through MLB results.
- MLB player metrics now join the official MLB Stats API and measured Baseball Savant wOBA by player ID. Both import paths write the same schema; ambiguous names are excluded rather than merged.
- Soccer refresh retries temporary transport/server failures. Source-derived goal estimates remain labeled as estimates.
- Grading backs up first; exceptional historical cleanup writes an exact deletion manifest. A fresh reporting period does not erase settled history.

## Coverage and limits

Runners cover MLB/KBO, soccer, ATP/WTA and tennis research, NFL/NCAAF, basketball and Czech Liga Pro table tennis. Coverage is source-dependent: Challenger identity/history, doubles, international basketball markets and point-level table-tennis finals can be incomplete. Some legacy/advanced paths still contain assumptions and require further hardening; guard coverage is not universal.

The October refresh recovered MLB player data and France soccer data. The public table-tennis recent-results page was unreadable; that refresh remains a reported failure. Hourly local grading retries available results when the desktop automation is running, preserves unresolved active fixtures and sends no Discord messages. Its configured cadence is local operational setup, not a guarantee for other repository users.

## Reliability and contribution

Predictions, results, price provenance and grading share `multisport_history.db`. Backups and detailed runtime snapshots remain local. Credentials belong in `.env`, which is ignored by Git. Never load untrusted serialized model files. Follow source access terms and retain provenance when adapting an ingest.

The current review is documented in [repository review and priorities](docs/REPOSITORY_REVIEW_2026-10-19.md). Contributions should include a reproducible defect or improvement, meaningful pass/failure tests, and an update to affected commands and data contracts. Research output, delivered recommendations and actual bets must remain distinct.
