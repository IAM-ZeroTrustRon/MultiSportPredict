import unittest

import msp_workflow as workflow
from features.basketball_props import (
    appearance_windows,
    combo_means,
    dedupe,
    has_minutes,
    history_before,
    is_appearance,
    per_minute_rates,
    to_float,
    validate_row,
)
from models.basketball_props import (
    availability_decision,
    baseline_minutes,
    candidate_minutes,
    chronological_split,
    clamp_minutes,
    fit_minutes_model,
    project_player,
    validate,
)


def row(player="p1", event="e1", date="2026-04-01", minutes=30.0, team="14",
        status="played", starter=True, points=20.0, rebounds=8.0, assists=5.0,
        overtime=False, reason=None, opponent="2"):
    return {
        "player_id": player, "player_name": player, "team_id": team, "team": "T",
        "opponent_id": opponent, "event_id": event, "game_date": date,
        "game_datetime": f"{date}T00:00:00Z", "season": int(date[:4]),
        "competition": "NBA", "status": status, "starter": starter,
        "did_not_play": status == "dnp", "reason": reason,
        "minutes": None if status == "dnp" else (0.0 if minutes == 0 else minutes),
        "points": None if status == "dnp" else points,
        "rebounds": None if status == "dnp" else rebounds,
        "assists": None if status == "dnp" else assists,
        "overtime": overtime, "periods": 5 if overtime else 4,
        "source": "test", "retrieved_at": "2026-10-26T00:00:00Z",
    }


def series(count, start_day=1, **overrides):
    rows = []
    for index in range(count):
        payload = dict(overrides)
        payload.setdefault("event", f"e{index}")
        payload.setdefault("date", f"2026-04-{start_day + index:02d}")
        rows.append(row(**payload))
    return rows


class ParsingTests(unittest.TestCase):
    def test_unavailable_is_not_zero(self):
        self.assertIsNone(to_float("--"))
        self.assertIsNone(to_float(""))
        self.assertIsNone(to_float(None))
        self.assertEqual(0.0, to_float("0"))
        self.assertEqual(31.0, to_float("31"))

    def test_dnp_and_zero_minute_appearance_are_distinct(self):
        dnp = row(status="dnp", minutes=0, event="e1")
        zero = row(minutes=0, event="e2")
        self.assertFalse(is_appearance(dnp))
        self.assertFalse(has_minutes(dnp))
        self.assertTrue(is_appearance(zero))
        self.assertFalse(has_minutes(zero))

    def test_duplicate_player_game_is_collapsed(self):
        played = row(event="e1", minutes=30.0)
        duplicate = row(event="e1", status="dnp", minutes=0)
        collapsed = dedupe([duplicate, played])
        self.assertEqual(1, len(collapsed))
        self.assertEqual("played", collapsed[0]["status"])


class ValidationTests(unittest.TestCase):
    def test_impossible_minutes_rejected(self):
        self.assertTrue(validate_row(row(minutes=90.0)))
        self.assertTrue(validate_row(row(minutes=-1.0)))

    def test_competition_mismatch_rejected(self):
        bad = row()
        bad["competition"] = "NZNBL"
        self.assertTrue(any("competition" in problem for problem in validate_row(bad)))

    def test_dnp_carrying_minutes_rejected(self):
        bad = row(status="dnp")
        bad["minutes"] = 22.0
        self.assertTrue(validate_row(bad))

    def test_clean_row_passes(self):
        self.assertEqual([], validate_row(row()))


class LeakageTests(unittest.TestCase):
    def test_target_game_and_later_dates_are_excluded(self):
        rows = [row(event="old", date="2026-04-01"), row(event="target", date="2026-04-05"),
                row(event="later", date="2026-04-09")]
        kept = history_before(rows, "2026-04-05", target_event_id="target")
        self.assertEqual(["old"], [r["event_id"] for r in kept])

    def test_same_day_game_never_leaks(self):
        rows = [row(event="a", date="2026-04-05"), row(event="b", date="2026-04-05")]
        self.assertEqual([], history_before(rows, "2026-04-05"))

    def test_windows_use_only_prior_appearances(self):
        rows = series(6, start_day=1)
        rows.append(row(event="future", date="2026-04-30", minutes=48.0))
        features = appearance_windows(rows, "2026-04-04")
        self.assertEqual(3, features["n_appearances"])
        self.assertEqual(30.0, features["windows"][5]["minutes_mean"])


class WindowTests(unittest.TestCase):
    def test_dnp_excluded_from_appearance_windows_but_counted(self):
        rows = [row(event="e1", date="2026-04-01", minutes=30.0),
                row(event="e2", date="2026-04-02", status="dnp", minutes=0, reason="COACH'S DECISION"),
                row(event="e3", date="2026-04-03", minutes=20.0)]
        features = appearance_windows(rows, "2026-04-04")
        self.assertEqual(2, features["n_appearances"])
        self.assertEqual(1, features["n_dnp"])
        self.assertEqual(25.0, features["windows"][10]["minutes_mean"])
        self.assertIn("COACH'S DECISION", features["dnp_reason_counts"])

    def test_overtime_flagged_and_rate_exclusion_possible(self):
        rows = [row(event="e1", date="2026-04-01", minutes=40.0, overtime=True),
                row(event="e2", date="2026-04-02", minutes=20.0, overtime=False)]
        features = appearance_windows(rows, "2026-04-03")
        self.assertEqual(0.5, features["overtime_share"])
        with_ot = per_minute_rates(rows)
        without_ot = per_minute_rates(rows, exclude_overtime=True)
        self.assertNotAlmostEqual(with_ot["points"], without_ot["points"])

    def test_trade_keeps_history_and_reports_team_change(self):
        rows = [row(event="e1", date="2026-04-01", team="15"),
                row(event="e2", date="2026-04-02", team="14")]
        features = appearance_windows(rows, "2026-04-03")
        self.assertEqual(2, features["team_changes_20"])
        self.assertEqual(2, features["n_appearances"])

    def test_missed_games_measured_against_team_schedule(self):
        player_rows = [row(event="e1", date="2026-04-01")]
        team_rows = [row(event="e1", date="2026-04-01"), row(event="e2", date="2026-04-03"),
                     row(event="e3", date="2026-04-05")]
        features = appearance_windows(player_rows, "2026-04-06", team_rows)
        self.assertEqual(3, features["team_games_scheduled"])
        self.assertEqual(2, features["missed_team_games"])

    def test_rest_days_from_calendar(self):
        rows = [row(event="e1", date="2026-04-01")]
        features = appearance_windows(rows, "2026-04-05")
        self.assertEqual(4, features["rest_days"])


class AvailabilityTests(unittest.TestCase):
    def test_out_and_doubtful_are_refused(self):
        for designation in ("OUT", "DOUBTFUL", "Suspension"):
            decision = availability_decision(designation)
            self.assertTrue(decision["refuse"], designation)

    def test_unknown_availability_is_research_only(self):
        decision = availability_decision(None)
        self.assertFalse(decision["refuse"])
        self.assertFalse(decision["actionable"])
        self.assertEqual("unknown", decision["level"])

    def test_refused_player_produces_no_projection(self):
        projection = project_player(appearance_windows(series(10), "2026-04-30"), None, "OUT")
        self.assertTrue(projection["refused"])
        self.assertNotIn("projected_minutes", projection)

    def test_insufficient_history_refused(self):
        projection = project_player(appearance_windows(series(2), "2026-04-30"), None, None)
        self.assertTrue(projection["refused"])
        self.assertEqual("INSUFFICIENT_HISTORY", projection["status"])


class MinutesModelTests(unittest.TestCase):
    def test_clamp_respects_regulation_and_overtime(self):
        self.assertEqual(48.0, clamp_minutes(60.0))
        self.assertEqual(60.0, clamp_minutes(60.0, allow_overtime=True))
        self.assertEqual(0.0, clamp_minutes(-5.0))
        self.assertIsNone(clamp_minutes(float("nan")))

    def test_baseline_prefers_ten_then_five_then_season(self):
        features = {"windows": {5: {"n": 5, "minutes_mean": 20.0}, 10: {"n": 10, "minutes_mean": 30.0},
                                20: {"n": 20, "minutes_mean": 40.0}}, "minutes_season_mean": 25.0}
        self.assertEqual(30.0, baseline_minutes(features))
        features["windows"][10]["minutes_mean"] = None
        self.assertEqual(20.0, baseline_minutes(features))

    def test_baseline_skips_a_window_supported_by_one_game(self):
        # A single appearance is not a rotation mean; fall through to the next
        # window that has a real sample.
        features = {"windows": {5: {"n": 5, "minutes_mean": 20.0}, 10: {"n": 1, "minutes_mean": 41.0},
                                20: {"n": 20, "minutes_mean": 30.0}}, "minutes_season_mean": 25.0}
        self.assertEqual(20.0, baseline_minutes(features))

    def test_candidate_needs_a_fitted_model(self):
        features = appearance_windows(series(10), "2026-04-30")
        self.assertIsNone(candidate_minutes(features, None))

    def test_fit_refuses_a_thin_sample(self):
        self.assertIsNone(fit_minutes_model([([1, 2, 3, 4, 5], 30.0)] * 5))

    def test_minutes_restriction_caps_projection(self):
        features = appearance_windows(series(10, minutes=36.0), "2026-04-30")
        projection = project_player(features, None, None, minutes_restriction=24.0)
        self.assertEqual(24.0, projection["projected_minutes"])
        self.assertIn("restriction", projection["minutes_basis"])


class ProjectionTests(unittest.TestCase):
    def test_research_projection_has_no_betting_output(self):
        projection = project_player(appearance_windows(series(10), "2026-04-30"), None, None)
        self.assertTrue(projection["research_only"])
        for forbidden in ("ev", "probability", "stake", "recommendation", "kelly"):
            self.assertNotIn(forbidden, projection)

    def test_combo_is_sum_of_component_means(self):
        means = {"points": 20.0, "rebounds": 8.0, "assists": 5.0}
        combos = combo_means(means)
        self.assertEqual(33.0, combos["pra"])
        self.assertEqual(25.0, combos["pa"])
        self.assertEqual(13.0, combos["ra"])

    def test_combo_none_when_a_component_is_missing(self):
        self.assertIsNone(combo_means({"points": 20.0, "rebounds": None, "assists": 5.0})["pra"])

    def test_projected_stats_scale_with_minutes(self):
        features = appearance_windows(series(10, minutes=30.0, points=15.0), "2026-04-30")
        projection = project_player(features, None, None)
        self.assertAlmostEqual(0.5, projection["per_minute"]["points"])
        self.assertAlmostEqual(15.0, projection["projected_stats"]["points"])


class SplitTests(unittest.TestCase):
    def test_split_keeps_whole_dates_together(self):
        rows = []
        for day in range(1, 11):
            rows.append(row(event=f"a{day}", date=f"2026-04-{day:02d}"))
            rows.append(row(event=f"b{day}", date=f"2026-04-{day:02d}"))
        train, test, cut = chronological_split(rows, 0.6)
        self.assertEqual(set(), {r["game_date"] for r in train} & {r["game_date"] for r in test})
        self.assertTrue(all(r["game_date"] < cut for r in train))
        self.assertTrue(all(r["game_date"] >= cut for r in test))

    def test_split_refuses_too_few_dates(self):
        train, test, cut = chronological_split(series(2), 0.6)
        self.assertEqual([], train)
        self.assertIsNone(cut)

    def test_validate_reports_both_baseline_and_candidate(self):
        rows = []
        for day in range(1, 21):
            for player in ("p1", "p2", "p3", "p4", "p5", "p6"):
                rows.append(row(player=player, event=f"e{player}{day}",
                                date=f"2026-04-{day:02d}", minutes=20.0 + day))
        report = validate(rows)
        self.assertEqual("ok", report["status"])
        self.assertIsNotNone(report["minutes_model"])
        self.assertGreater(report["played_game_accuracy"]["candidate"]["n"], 0)
        self.assertEqual(report["played_game_accuracy"]["baseline"]["n"],
                         report["played_game_accuracy"]["candidate"]["n"])


class SeasonScopeTests(unittest.TestCase):
    @staticmethod
    def _labelled(day, minutes, label, event):
        payload = row(event=event, date=day, minutes=minutes)
        payload["season_label"] = label
        return payload

    def test_current_season_rotation_is_not_pooled_with_last_season(self):
        # Last April was played on rest days with a different roster; three games
        # of this season say far more about tonight's role.
        prior = [self._labelled(f"2026-04-{day:02d}", minutes, "2025-26", f"a{day}")
                 for day, minutes in zip(range(1, 7), (24.0, 30.0, 28.0, 26.0, 30.0, 29.0))]
        current = [self._labelled(f"2026-10-{day:02d}", 36.0, "2026-27", f"b{day}")
                   for day in (20, 22, 25)]
        features = appearance_windows(prior + current, "2026-10-26", target_season="2026-27")
        self.assertEqual("current_season", features["window_scope"])
        self.assertEqual(36.0, features["windows"][10]["minutes_mean"])
        self.assertEqual(3, features["windows"][10]["n"])
        # Minutes are scoped to the season, but the per-minute rate falls back to
        # the wider recent sample when the same-season sample is thin.
        self.assertEqual(3, features["rates_last10"]["_appearances"])
        self.assertEqual(9, features["rates_all"]["_appearances"])
        self.assertEqual("all_appearances", project_player(features)["rate_window"])
        self.assertFalse(features["stale_rotation"])

    def test_thin_current_season_is_disclosed_as_carryover(self):
        prior = [self._labelled(f"2026-04-{day:02d}", 30.0, "2025-26", f"a{day}")
                 for day in range(1, 7)]
        current = [self._labelled(f"2026-10-{day:02d}", 36.0, "2026-27", f"b{day}")
                   for day in (20, 22)]
        features = appearance_windows(prior + current, "2026-10-26", target_season="2026-27")
        self.assertEqual("prior_season_carryover", features["window_scope"])
        self.assertTrue(features["stale_rotation"])
        self.assertTrue(any("carried over" in reason for reason in features["stale_reasons"]))
        self.assertEqual(8, features["n_window_appearances"])


class WorkflowRoutingTests(unittest.TestCase):
    def test_props_route_to_the_props_runner(self):
        command = workflow.run_command("basketball", ["A vs B"], "2026-10-28", "NBA",
                                       {"props": True}, [])
        self.assertEqual("run_basketball_props.py", command[0])
        self.assertIn("--date", command)

    def test_props_require_a_league(self):
        with self.assertRaises(ValueError):
            workflow.run_command("basketball", ["A vs B"], "2026-10-28", None, {"props": True}, [])

    def test_dry_run_is_a_preview_not_a_failure(self):
        self.assertEqual((True, "preview"), workflow.run_status(0, False, dry_run=True))

    def test_dry_run_with_bad_exit_still_fails(self):
        self.assertEqual((False, "failed"), workflow.run_status(2, False, dry_run=True))

    def test_real_run_without_artifact_still_fails(self):
        self.assertEqual((False, "failed"), workflow.run_status(0, False, dry_run=False))

    def test_real_run_with_artifact_is_saved(self):
        self.assertEqual((True, "saved"), workflow.run_status(0, True, dry_run=False))


if __name__ == "__main__":
    unittest.main()
