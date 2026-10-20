# Retained historical model record — October 19, 2026

This snapshot describes stored model selections. It is **not an audited betting record**, proof of wagers placed, or proof of future profitability. The October 20 reporting period is separate and begins with zero graded selections.

| Scope | Graded | Wins | Losses | Pushes | Win rate |
|---|---:|---:|---:|---:|---:|
| Retained ordinary selections | 379 | 181 | 195 | 3 | 48.14% |
| Recorded-price subset | 238 | 112 | 124 | 2 | 47.46% |

Recorded-price subset: **+20.2397 simulated units**, **+8.50% simulated ROI**, risking one unit per selection including pushes in the stake denominator. Win rate excludes pushes. Positive returns with a sub-50% win rate are possible because payoffs depend on odds. This is descriptive arithmetic over retained records, not evidence of a stable edge.

141 historical grades lack a confirmed recorded-price settlement. They contribute to outcome counts but are excluded from the showcased unit return and ROI. Recommendations include BET and LEAN decisions; PASS/INFO/VOID and duplicate reruns are excluded. Different markets on one event can be correlated. Table-tennis research selections are reported separately and currently have zero verified grades.

| Stored sport | Wins | Losses | Pushes | Win rate |
|---|---:|---:|---:|---:|
| baseball | 53 | 54 | 1 | 49.53% |
| ncaaf | 57 | 77 | 1 | 42.54% |
| nfl | 44 | 49 | 1 | 47.31% |
| soccer | 4 | 0 | 0 | 100.00% |
| tennis | 23 | 15 | 0 | 60.53% |

## Cleanup disclosure

On October 19, verified result recovery added 31 grades. After backup, 47 unresolved historical ordinary rows (including duplicate reruns) and 18 unresolved table-tennis runs were deleted at the owner's request. Settled history was retained. These exclusions mean this snapshot **cannot represent the complete original recommendation population**; cleanup introduces selection/missing-outcome bias. It must not be marketed as a fully settled prospective track record.

Two active selections for the October 19 San Francisco–Washington game remain awaiting a confirmed final; two older reruns of that same live event remain excluded duplicates. Future/in-progress events were preserved. Missing canceled-game settlement rules and the conflicting Machac–Muller fixture were not converted into fabricated pushes or wins.

## Reproduce the current figures

From Git Bash in `/c/MultiSportPredict`:

```bash
venv/Scripts/python.exe -u msp.py record --all-time
venv/Scripts/python.exe -u msp.py record
venv/Scripts/python.exe -u msp.py pending
```

The live record will change as new finals arrive. This dated document remains a fixed snapshot. The machine-readable companion is [performance_snapshot_2026-10-19.json](performance_snapshot_2026-10-19.json).

## What a stronger prospective record needs

Freeze picks, event identities, market definitions, price and capture time before start; record every issued recommendation and delivery receipt; retain unresolved/canceled selections with explicit exclusion reasons in an evaluation archive; evaluate calibration and closing prices by sport/market; report flat-stake returns, drawdown and uncertainty over a prospective period. Logging deliveries is not evidence of wagering, and a closing-line comparison is not yet a complete, verified dataset here.
