# ATP Montreal (National Bank Open) — 3 Matches -> Discord

## Goal
Run all three ATP Montreal Round-of-32 hard-court matches through the real Elo
tennis model, seed the six players into the Elo data so the model is no longer
a 50/50 coin-flip, and push all three consolidated value-play recommendations
to the Discord recommendations webhook.

## Matches
1. Daniel Merida Aguilar vs Alex Michelsen
2. Zizou Bergs vs Ben Shelton
3. Learner Tien vs Tommy Paul

## Steps
- [x] Seed Daniel Merida Aguilar + Alex Michelsen + Zizou Bergs + Ben Shelton +
      Learner Tien + Tommy Paul 2026 hard-court results into
      `models/tennis_elo.py` so the model produces differentiated probabilities.
- [x] Create `run_montreal_atp_three_matches_to_discord.py` that runs all three
      matches through the real Elo model, routes confidence through the core
      engine, attaches the consolidated value-plays for each match, and pushes
      each to Discord via `push_recommendation_to_discord`.
- [x] Dry-run the script to verify all three payloads render sensible probabilities.
- [x] Run (non-dry-run) to push all three recommendations to Discord.

## Verification
- [x] Dry-run prints all three combined model + value-play payloads.
- [x] Live run confirms Discord push succeeds (`[SUCCESS]`).
