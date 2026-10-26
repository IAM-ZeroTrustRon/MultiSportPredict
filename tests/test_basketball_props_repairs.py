import datetime as dt
import unittest

import basketball_availability as availability
from features.basketball_props import (
    APPEARED,
    DID_NOT_PLAY,
    UNVERIFIED,
    appearance_windows,
    minutes_observation,
)
from ingest_basketball_props import parse_summary, season_label_for
from models.basketball_props import availability_decision, project_player, validate
from run_basketball_props import assert_projectable, format_research

UTC = dt.timezone.utc
FRESH = dt.datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def row(player="p1", event="e1", date="2026-04-01", minutes=30.0, status="played",
        season="2025-26", team="14", starter=True, points=20.0, rebounds=8.0,
        assists=5.0):
    return {
        "player_id": player, "player_name": player, "team_id": team, "team": "T",
        "opponent_id": "2", "event_id": event, "game_date": date,
        "game_datetime": f"{date}T00:00:00Z", "season": 2026, "season_label": season,
        "competition": "NBA", "status": status, "starter": starter,
        "did_not_play": status == "dnp",
        "minutes": None if status == "dnp" else (0.0 if minutes == 0 else minutes),
        "points": None if status == "dnp" else points,
        "rebounds": None if status == "dnp" else rebounds,
        "assists": None if status == "dnp" else assists,
        "overtime": False, "periods": 4, "source": "test", "retrieved_at": "2026-10-26T00:00:00Z",
    }


def series(count, start_day=1, **overrides):
    rows = []
    for index in range(count):
        payload = dict(overrides)
        payload.setdefault("event", f"e{index}")
        payload.setdefault("date", f"2026-04-{start_day + index:02d}")
        rows.append(row(**payload))
    return rows


class UnknownAvailabilityTests(unittest.TestCase):
    """Repair 1: unknown must never become available."""

    def test_missing_designation_is_not_actionable(self):
        decision = availability_decision(None)
        self.assertFalse(decision["actionable"])
        self.assertFalse(decision["refuse"])
        self.assertEqual("unknown", decision["level"])

    def test_blank_designation_is_not_actionable(self):
        self.assertFalse(availability_decision("")["actionable"])
        self.assertFalse(availability_decision("   ")["actionable"])

    def test_player_absent_from_fresh_report_is_unknown(self):
        snapshot = {"fresh": True, "players": {}}
        self.assertIsNone(availability.designation_for(snapshot, "999"))
        self.assertFalse(availability_decision(
            availability.designation_for(snapshot, "999"))["actionable"])

    def test_stale_snapshot_yields_no_designation(self):
        snapshot = {"fresh": False, "players": {"1": {"designation": "OUT"}}}
        self.assertIsNone(availability.designation_for(snapshot, "1"))

    def test_projection_with_unknown_availability_is_not_actionable(self):
        projection = project_player(appearance_windows(series(10), "2026-04-30"), None, None)
        self.assertFalse(projection["availability"]["actionable"])
        self.assertTrue(any("availability" in w for w in projection["warnings"]))

    def test_only_explicit_clearance_is_actionable(self):
        for cleared in ("AVAILABLE", "ACTIVE", "CLEARED", "  available  "):
            self.assertTrue(availability_decision(cleared)["actionable"], cleared)

    def test_unrecognised_prose_never_grants_actionable_status(self):
        for text in ("REPORT NOT SUBMITTED", "NOT AVAILABLE", "EXPECTED TO PLAY", "OK",
                     "HEALTHY", "UNSPECIFIED", "N/A", "PENDING", "WAIVED"):
            decision = availability_decision(text)
            self.assertFalse(decision["actionable"], text)
            self.assertFalse(decision["refuse"], text)
            self.assertEqual("unknown", decision["level"], text)

    def test_unrecognised_status_names_itself_in_the_note(self):
        decision = availability_decision("REPORT NOT SUBMITTED")
        self.assertIn("REPORT NOT SUBMITTED", decision["note"])


class MissingValueDisplayTests(unittest.TestCase):
    """Repair 2: a missing projection is --, never 0.0."""

    def document(self, refused):
        row_data = {
            "player": "Test Player", "side": "home", "player_id": "1",
            "n_appearances": 5, "last_appearance_season": "2025-26", "windows": {},
            "projected_minutes": None, "projected_stats": {}, "projected_combos": {},
            "availability": {"level": "unknown", "actionable": False},
            "refused": refused, "status": "REFUSED", "reason": "player is unavailable",
        }
        return {"date": "2026-10-28", "store_games": 1, "store_rows": 1,
                "store_seasons": ["2026-27"], "store_source": "test", "store_updated": "today",
                "cutoff_rule": "strict", "availability": [], "rows": [row_data],
                "no_betting_output": "none"}

    def test_refused_row_prints_dashes_not_zeros(self):
        text = format_research(self.document(refused=True))
        line = [l for l in text.splitlines() if l.startswith("Test Player")][0]
        self.assertIn("--", line)
        self.assertNotIn("0.0", line)

    def test_missing_minutes_never_render_as_zero(self):
        text = format_research(self.document(refused=False))
        line = [l for l in text.splitlines() if l.startswith("Test Player")][0]
        self.assertNotIn("0.0", line)


class SeasonIdentityTests(unittest.TestCase):
    """Repair 3: verified season IDs, with off-season and stale flags."""

    def test_calendar_year_is_not_a_season(self):
        self.assertEqual("2025-26", season_label_for(2026))
        self.assertEqual("2026-27", season_label_for(2027))
        self.assertIsNone(season_label_for(None))

    def test_parse_summary_uses_feed_season_not_game_year(self):
        payload = {
            "header": {"season": {"year": 2027, "type": 2, "displayName": "2026-27"},
                       "competitions": [{"competitors": [
                           {"homeAway": "home", "team": {"id": "14", "displayName": "Heat"}},
                           {"homeAway": "away", "team": {"id": "15", "displayName": "Bucks"}}]}]},
            "boxscore": {"players": [{"team": {"id": "14", "displayName": "Heat"},
                                      "statistics": [{"names": ["MIN", "PTS", "REB", "AST"],
                                                      "athletes": [{"athlete": {"id": "1", "displayName": "A"},
                                                                    "starter": True, "didNotPlay": False,
                                                                    "stats": ["30", "20", "8", "5"]}]}]}]},
        }
        event = {"id": "9", "date": "2026-10-21T00:00:00Z", "name": "A at B"}
        rows = parse_summary(event, payload, "2026-10-26T00:00:00Z")
        self.assertEqual(1, len(rows))
        self.assertEqual(2027, rows[0]["season"])
        self.assertEqual("2026-27", rows[0]["season_label"])

    def test_previous_season_history_is_flagged(self):
        features = appearance_windows(series(6, season="2025-26"), "2026-10-28",
                                      target_season="2026-27")
        self.assertTrue(features["crosses_season"])
        self.assertTrue(features["stale_rotation"])

    def test_current_season_history_is_not_flagged_stale(self):
        features = appearance_windows(series(6, season="2026-27"), "2026-10-28",
                                      target_season="2026-27")
        self.assertFalse(features["crosses_season"])

    def test_long_gap_is_flagged_stale(self):
        features = appearance_windows(series(3, season="2026-27"), "2026-10-28",
                                      target_season="2026-27")
        self.assertTrue(features["stale_rotation"])


class ValidationSeparationTests(unittest.TestCase):
    """Repair 4: played-game accuracy and participation are reported separately."""

    def build(self):
        rows = []
        for day in range(1, 21):
            for player in ("p1", "p2", "p3", "p4", "p5", "p6"):
                status = "dnp" if (day % 5 == 0 and player in ("p1", "p2")) else "played"
                rows.append(row(player=player, event=f"{player}-{day}",
                                date=f"2026-04-{day:02d}", minutes=20.0 + day,
                                status=status, season="2025-26"))
        return rows

    def test_report_separates_the_two_questions(self):
        report = validate(self.build())
        self.assertEqual("ok", report["status"])
        self.assertIn("played_game_accuracy", report)
        self.assertIn("participation_inclusive", report)
        self.assertIn("participation", report)
        self.assertNotEqual(report["played_game_accuracy"], report["participation_inclusive"])

    def test_dnp_rows_are_counted_in_participation(self):
        report = validate(self.build())
        self.assertGreater(report["participation"]["did_not_play"], 0)
        self.assertGreater(report["participation"]["appeared"], 0)
        self.assertAlmostEqual(
            report["participation"]["appeared"]
            / (report["participation"]["appeared"] + report["participation"]["did_not_play"]),
            report["participation"]["appearance_rate"])

    def test_participation_inclusive_includes_dnp_rows(self):
        report = validate(self.build())
        self.assertGreater(report["participation_inclusive"]["baseline"]["n"],
                           report["played_game_accuracy"]["baseline"]["n"])

    def test_baseline_and_candidate_stats_are_separate(self):
        report = validate(self.build())
        self.assertIn("baseline", report["stat_projection_error"])
        self.assertIn("candidate", report["stat_projection_error"])


class FixtureGuardTests(unittest.TestCase):
    """Repair 5: date, kickoff and status are enforced."""

    def event(self, status="STATUS_SCHEDULED", kickoff="2026-10-28T23:00:00Z"):
        return {"id": "1", "date": kickoff, "name": "A at B",
                "competitions": [{"status": {"type": {"name": status}}, "date": kickoff}]}

    def test_finished_game_is_refused(self):
        with self.assertRaises(ValueError):
            assert_projectable(self.event(status="STATUS_FINAL"), "2026-10-28", FRESH)

    def test_in_progress_game_is_refused(self):
        with self.assertRaises(ValueError):
            assert_projectable(self.event(status="STATUS_IN_PROGRESS"), "2026-10-28", FRESH)

    def test_already_started_kickoff_is_refused(self):
        with self.assertRaises(ValueError):
            assert_projectable(self.event(kickoff="2026-10-26T10:00:00Z"), "2026-10-26",
                               FRESH)

    def test_date_mismatch_is_refused(self):
        with self.assertRaises(ValueError):
            assert_projectable(self.event(), "2026-10-29", FRESH)

    def test_scheduled_future_fixture_is_accepted(self):
        kickoff = assert_projectable(self.event(), "2026-10-28", FRESH)
        self.assertEqual(28, kickoff.day)

    def test_missing_kickoff_is_refused(self):
        event = {"id": "1", "name": "A at B", "competitions": [{"status": {"type": {"name": "STATUS_SCHEDULED"}}}]}
        with self.assertRaises(ValueError):
            assert_projectable(event, "2026-10-28", FRESH)


class EventScopedAvailabilityTests(unittest.TestCase):
    """Repair 6: freshness comes from the fixture's own payload, not another endpoint."""

    def payload(self, designations=None, header_id="1", home="1", away="2", season=2027):
        blocks = [{"team": {"id": team_id, "displayName": name}, "injuries": entries}
                  for team_id, name, entries in (designations or [])]
        return {
            "header": {
                "id": header_id,
                "season": {"year": season, "type": 2},
                "competitions": [{
                    "id": header_id,
                    "date": "2026-10-28T23:00:00Z",
                    "status": {"type": {"name": "STATUS_SCHEDULED"}},
                    "competitors": [
                        {"homeAway": "home", "team": {"id": home, "displayName": "Hawks"}},
                        {"homeAway": "away", "team": {"id": away, "displayName": "Heat"}},
                    ],
                }],
            },
            "injuries": blocks,
        }

    def loader(self, designations=None, urls=None, **kwargs):
        payload = self.payload(designations, **kwargs)

        def fetch(url):
            if urls is not None:
                urls.append(url)
            return payload
        return fetch

    def patient(self, player_id="4712863", status="Out", date="2026-10-26T09:00:00Z"):
        return {"status": status, "date": date,
                "athlete": {"id": player_id, "displayName": "Mouhamed Gueye"}}

    def test_fresh_event_snapshot_exposes_designation(self):
        urls = []
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient()])], urls=urls))
        self.assertTrue(snapshot["fresh"])
        self.assertTrue(snapshot["identity"]["verified"])
        self.assertEqual("OUT", availability.designation_for(snapshot, "4712863", FRESH))
        self.assertEqual("2026-27", snapshot["season"]["label"])

    def test_no_second_endpoint_is_consulted_for_freshness(self):
        urls = []
        availability.snapshot("1", now=FRESH, fetch=self.loader([], urls=urls))
        self.assertEqual(1, len(urls))
        self.assertIn("summary?event=1", urls[0])
        self.assertFalse(hasattr(availability, "LEAGUE_SOURCE"))

    def test_snapshot_age_is_rechecked_when_read(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient()])]))
        later = FRESH + dt.timedelta(hours=availability.MAX_SNAPSHOT_AGE_HOURS + 1)
        self.assertIsNone(availability.designation_for(snapshot, "4712863", later))
        self.assertEqual("OUT", availability.designation_for(snapshot, "4712863", FRESH))

    def test_future_retrieved_at_is_corrupt_not_fresh(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient()])]))
        earlier = FRESH - dt.timedelta(hours=1)
        self.assertIsNone(availability.designation_for(snapshot, "4712863", earlier))

    def test_event_identity_mismatch_is_not_fresh(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient()])], header_id="999"))
        self.assertFalse(snapshot["fresh"])
        self.assertFalse(snapshot["identity"]["verified"])
        self.assertEqual({}, snapshot["players"])

    def test_designation_for_foreign_team_is_rejected(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("77", "Celtics", [self.patient()])]))
        self.assertIsNone(availability.designation_for(snapshot, "4712863", FRESH))
        self.assertEqual(1, len(snapshot["rejected_designations"]))
        self.assertIn("not competing", snapshot["rejected_designations"][0]["reason"])

    def test_future_designation_date_is_rejected(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient(date="2026-11-02T09:00:00Z")])]))
        self.assertEqual({}, snapshot["players"])
        self.assertIn("future", snapshot["rejected_designations"][0]["reason"])

    def test_old_designation_is_disclosed_not_deleted(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient(date="2026-09-21T19:50:00Z")])]))
        entry = snapshot["players"]["4712863"]
        self.assertTrue(entry["designation_older_than_limit"])
        self.assertGreater(entry["designation_age_hours"], 24)
        self.assertEqual("OUT", availability.designation_for(snapshot, "4712863", FRESH))

    def test_undated_designation_is_kept_but_flagged(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [self.patient(date=None)])]))
        entry = snapshot["players"]["4712863"]
        self.assertTrue(entry["designation_undated"])
        self.assertIsNone(entry["designation_age_hours"])

    def test_missing_athlete_id_is_rejected(self):
        snapshot = availability.snapshot("1", now=FRESH, fetch=self.loader(
            [("1", "Hawks", [{"status": "Out", "date": "2026-10-26T09:00:00Z",
                              "athlete": {"displayName": "No Id"}}])]))
        self.assertEqual({}, snapshot["players"])
        self.assertIn("athlete id", snapshot["rejected_designations"][0]["reason"])

    def test_network_failure_does_not_imply_available(self):
        def boom(url):
            raise OSError("offline")
        snapshot = availability.snapshot("1", now=FRESH, fetch=boom)
        self.assertFalse(snapshot["fresh"])
        self.assertEqual({}, snapshot["players"])
        self.assertIsNone(availability.designation_for(snapshot, "1", FRESH))

    def test_availability_decisions_for_published_statuses(self):
        self.assertTrue(availability_decision("OUT")["refuse"])
        uncertain = availability_decision("DAY-TO-DAY")
        self.assertFalse(uncertain["refuse"])
        self.assertFalse(uncertain["actionable"])


class PostgameTriStateTests(unittest.TestCase):
    """Repair 3: unverified observations are excluded, never scored as zero."""

    def dataset(self):
        rows = []
        for day in range(1, 21):
            date = f"2026-04-{day:02d}"
            for player in ("p1", "p2", "p3", "p4", "p5", "p6"):
                if player == "p1" and day >= 13:
                    # Confirmed later, but this game was never observed.
                    rows.append(row(player=player, event=f"{player}-{day}", date=date,
                                    minutes=None, status="played"))
                elif player == "p2" and day == 14:
                    rows.append(row(player=player, event=f"{player}-{day}", date=date,
                                    minutes=None, status="dnp"))
                elif player == "p3" and day == 15:
                    rows.append(row(player=player, event=f"{player}-{day}", date=date,
                                    minutes=0.0, status="played"))
                else:
                    rows.append(row(player=player, event=f"{player}-{day}", date=date,
                                    minutes=20.0 + day, status="played"))
        return rows

    def test_classification_of_the_three_states(self):
        self.assertEqual((APPEARED, 0.0), minutes_observation(
            {"status": "played", "minutes": 0.0, "did_not_play": False}))
        self.assertEqual((APPEARED, 27.0), minutes_observation(
            {"status": "played", "minutes": 27.0, "did_not_play": False}))
        self.assertEqual((DID_NOT_PLAY, 0.0), minutes_observation(
            {"status": "dnp", "minutes": None, "did_not_play": True}))
        self.assertEqual((DID_NOT_PLAY, 0.0), minutes_observation(
            {"status": "dnp", "minutes": 0.0, "did_not_play": True}))

    def test_missing_observation_is_unverified(self):
        self.assertEqual((UNVERIFIED, None), minutes_observation(
            {"status": "played", "minutes": None, "did_not_play": False}))
        self.assertEqual((UNVERIFIED, None), minutes_observation(
            {"status": "unknown", "minutes": 12.0, "did_not_play": False}))

    def test_dnp_carrying_minutes_is_contradictory_not_trusted(self):
        self.assertEqual((UNVERIFIED, None), minutes_observation(
            {"status": "dnp", "minutes": 12.0, "did_not_play": True}))

    def test_unverified_rows_are_excluded_from_every_error_block(self):
        report = validate(self.dataset())
        participation = report["participation"]
        self.assertEqual(8, participation["unverified"])
        self.assertEqual(8, participation["excluded_from_error"])
        self.assertEqual(39, participation["appeared"])
        self.assertEqual(1, participation["did_not_play"])
        self.assertEqual(1, participation["listed_zero_minutes"])
        self.assertEqual(40, participation["confirmed_rows"])
        self.assertEqual(48, report["n_test_rows"])

    def test_inclusive_error_covers_confirmed_rows_only(self):
        report = validate(self.dataset())
        confirmed = (report["participation"]["appeared"]
                     + report["participation"]["did_not_play"])
        self.assertEqual(confirmed, report["participation_inclusive"]["baseline"]["n"])
        self.assertEqual(report["participation"]["appeared"],
                         report["played_game_accuracy"]["baseline"]["n"])

    def test_zero_minute_appearance_counts_as_appearance(self):
        report = validate(self.dataset())
        p3_rows = [r for r in self.dataset()
                   if r["player_id"] == "p3" and r["game_date"] == "2026-04-15"]
        self.assertEqual(0.0, minutes_observation(p3_rows[0])[1])
        self.assertGreater(report["participation"]["listed_zero_minutes"], 0)


if __name__ == "__main__":
    unittest.main()
