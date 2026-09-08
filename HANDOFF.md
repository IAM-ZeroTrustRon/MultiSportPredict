# MultiSportPredict — Handoff (SUPERSEDED)

**This document is superseded as of 2026-09-08. Read `STATE.md` instead.**

Everything below is the 2026-08-29 snapshot — kept for history only. It
predates: the soccer resolver fix, the MLB/NFL moneyline sign-bug fix,
tennis and NCAAF auto-grading, the soccer shots/tempo constant removal,
the three new soccer leagues, auto-fetched market odds, supersede-based
Discord dedup, and hitter props. Several claims in it (e.g. what grades
automatically, which sports have a graded record) are no longer accurate.

Go read `C:\MultiSportPredict\STATE.md`.

---

# MultiSportPredict — Handoff (original, 2026-08-29)

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

*(original document continues unchanged — see git history at commit
`421caee` or earlier for the full original text; truncated here since it is
superseded, not a live reference)*
