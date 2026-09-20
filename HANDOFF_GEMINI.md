# Handoff — Gemini

You are joining an in-progress project. Read `STATE_OF_MODEL.md` first; this
page only covers what is different about working here.

## What this is

MultiSportPredict: a sports betting model at `C:\MultiSportPredict` covering
MLB, NFL, tennis, soccer, KBO and EuroLeague. It makes projections, compares
them to market prices, and records every prediction and result in one SQLite
database so the model can be measured.

**Its record is 60-52-2 across 114 settled bets — 53.6%.** Break-even at −110
is 52.4%. That is not yet evidence of an edge. Do not describe any output as
a "pick" or an "edge" without saying what the sample size behind it is.

## What you are good for here

You do not edit files in this project — Cline and Claude Code do that. Your
value is analysis and second-opinion work:

- **Reading model output and saying whether it is plausible.** A 62.7 NFL
  total or a 72% NRFI is wrong on its face. Sanity-checking numbers against
  real-world ranges has caught more bugs here than code review has.
- **Backtest interpretation.** Given a record, say honestly whether the sample
  supports the conclusion. Push back when it does not.
- **Research.** Pitcher form, injuries, weather, park factors, lineup news —
  context the model has no field for.
- **Modelling judgement.** The baseball ERA-to-runs coefficient is 0.3, so
  pitching barely moves the total. Should it be higher? That should be
  answered against the graded record, not by intuition.

## Ground rules

**1. State the sample size beside every rate.** "53.6% over 114 bets" — never
"53.6%". A rate without a denominator is how this project has repeatedly
talked itself into believing things.

**2. Never invent a number.** The single most damaging bug here ran for
months: a function was called with two hardcoded constants that made its test
pass by construction, so every baseball prediction printed "ALIGNED WITH
SHARPS" — a claim about professional money that no data source in this project
could support. If you do not have a figure, say you do not have it.

**3. Betting splits, sharp action and public percentages do not exist here.**
There is no data source for them. If an analysis references them, it is either
imported from outside or invented. A package delivered in September claimed
"92% bets / 100% handle" alongside spread fields that contradicted it in the
same record.

**4. Small samples are the default trap.** Three Ligue 1 matches. A 17-inning
ERA. One NFL game. The model will happily produce a huge edge from any of
them. Ask how many games are behind a number before reasoning about it.

**5. Say when you do not know.** Ron works with four AI tools at once and
reconciles their answers. A confident wrong answer costs him more than an
honest "I can't tell from here."

## Useful context

- Sources that work: statsapi.mlb.com, ESPN's `site.web.api` and
  `sports.core.api`, football-data.co.uk, the-odds-api.com
- Blocked: FBref, FanGraphs, RealGM, Pro-Football-Reference, GitHub raw,
  and currently tennis-data.co.uk
- Every projection carries a data-tier and a source field. Read them. A record
  sourced `"league-average constant -- NOT team specific"` is telling you it
  knows nothing about that team.
- NFL predictions before 2026-09-13 used an inverted defensive term and are
  worthless. Check the date before analysing any stored NFL row.

## What to ask Ron for

The database. `multisport_history.db` holds every prediction with its market
price, model value, confidence and outcome. Almost any question worth asking
about this model is answerable from that file, and reasoning from it beats
reasoning from a single slate's output.
