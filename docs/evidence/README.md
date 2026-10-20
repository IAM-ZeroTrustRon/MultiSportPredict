# MultiSportPredict evidence

This section contains historical screenshots of actual project output, copied unchanged from the owner's local screenshot collection. Dates below come from screenshot filenames; displayed timestamps provide additional context where visible. These captures illustrate workflows, not verified betting performance. Existing images under `output/command_guides_20261011/` and `output/table_tennis/` are rendered documentation previews, not result evidence.

## Selected historical captures

### Tennis: market comparison — October 9, 2026

![Historical tennis recommendations and market comparisons](pricing/2026-10-09-tennis-market-comparison.png)

Shows Berrettini–Nakashima and Halys–Blockx output with model probabilities, moneyline prices, no-vig market references and displayed game-market EV. Several rows are explicitly labeled model-only/uncalibrated. This demonstrates the historical comparison interface; it does not validate those probabilities, EV estimates, fixture identities or final outcomes. Older presentation/encoding issues are preserved in the original capture.

### EuroLeague: an unpriced market remains a pass — October 9, 2026

![Historical EuroLeague output retaining PASS when no priced model value is available](validation/2026-10-09-euroleague-unpriced-pass.png)

Shows Olympiacos–Anadolu Efes output, source-tagged team metrics and `PASS — no priced model value` for spread/total markets. It illustrates why a model probability alone is insufficient to establish value at an offered price. It is not proof of universal guard coverage or calibrated accuracy.

### KBO: data refresh and an empty slate — October 7, 2026

![KBO ingestion success followed by an empty-date slate message](validation/2026-10-07-kbo-data-refresh.png)

The terminal reports ingestion of ten KBO teams, followed by `Nothing on today's schedule to run.` This documents source ingestion and the displayed slate outcome at that time. It is not evidence that a pick was issued, a wager was placed or a result was graded.

### Basketball: manual-input projection — October 9, 2026

![Historical Boras Basket versus BC Lulea manual-input model projection](picks/2026-10-09-boras-lulea-manual-input-projection.png)

Shows a Boras Basket–BC Lulea projection, a supplied spread/total and a saved JSON path. A companion capture from the same session shows explicit team-rating/pace overrides, so this is classified as a manual-input demonstration. The displayed point edge is not an EV percentage; the screenshot does not verify input provenance, fixture status, odds or a profitable outcome.

## Categories

| Folder | What belongs here | What it demonstrates |
|---|---|---|
| `picks/` | Full saved match/slate reviews and recommendation cards | The selection, market, price and model output at that time |
| `pricing/` | Timestamped odds comparisons, line discrepancies and EV displays | The market price used to evaluate value |
| `delivery/` | Discord cards and delivery confirmations | A recommendation was delivered; this does not establish a wager |
| `grading/` | Confirmed finals and corresponding settled selections | How a specific stored pick was graded |
| `performance/` | Dated record summaries, ROI reports and drawdown charts | Aggregate results with their sample, period and price coverage |
| `validation/` | Data/fixture refusals, test results and source diagnostics | Reliability checks and visible handling of unavailable data |

Create additional category folders when evidence is added. Use descriptive, dated filenames. Delivery, grading and performance screenshots are still needed; none of the selected captures establishes those claims. The root README links here for the complete collection.

## Captions and context

Each image entry should state its capture date, sport/market, the feature demonstrated, and any important limitation. Link a saved run or supporting report when available. Distinguish estimated EV, model selections, delivered recommendations and actual wagers. Label historical captures when the interface or record has changed.

Keep source images unchanged. Do not edit odds, dates, results or displayed figures. Review screenshots for credentials and private information before including them in a public commit. A dated screenshot illustrates a result; it does not replace the underlying record or establish long-term accuracy.

Performance evidence must retain the qualifications in [the historical performance disclosure](../PERFORMANCE_2026-10-19.md), including recorded-price coverage and the exclusion of unresolved historical outcomes during cleanup.
