import sys
from pathlib import Path
import json
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soccer_store import merge_records, competition_view, audit_records


def record(league, season=2026, games=8):
    return {"league": league, "season": season, "games": games,
            "goals_for": 2, "goals_against": 1, "updated": "2026-10-05"}


@pytest.mark.parametrize("reverse", [False, True])
def test_competitions_survive_both_ingestion_orders(reverse):
    domestic = {"Arsenal": record("Premier League")}
    europe = {"Arsenal": record("UEFA Champions League", games=1)}
    first, second = (europe, domestic) if reverse else (domestic, europe)
    store = merge_records(first, second)
    assert store["Arsenal"]["league"] == "Premier League"
    assert competition_view(store, "Premier League")["Arsenal"]["games"] == 8
    assert competition_view(store, "UEFA Champions League")["Arsenal"]["games"] == 1
    assert len(audit_records(store)) == 2
    assert not competition_view(store, "La Liga")


def test_prior_season_never_replaces_current_and_is_preserved():
    store = merge_records({"France": record("UEFA Nations League", 2026, 3)},
                          {"France": record("UEFA Nations League", 2024, 6)})
    assert competition_view(store, "UEFA Nations League")["France"]["season"] == 2026
    assert store["France"]["games"] == 3
    assert store["_competition_records"]["uefa nations league"]["2024"]["France"]["games"] == 6


def test_structured_season_and_legacy_records_share_identity():
    store = merge_records({"Arsenal": record("Premier League", "2026/2027")},
                          {"Arsenal": record("Premier League", {"year": 2026}, 9)})
    assert list(store["_competition_records"]["premier league"]) == ["2026"]
    assert competition_view(store, "EPL")["Arsenal"]["games"] == 9


def test_stats_provider_reads_requested_competition(tmp_path, monkeypatch):
    import team_stats_provider as provider
    store = merge_records({"Arsenal": record("Premier League")},
                          {"Arsenal": record("UEFA Champions League", games=1)})
    path = tmp_path / "auto.json"
    path.write_text(json.dumps(store))
    manual = tmp_path / "manual.json"
    manual.write_text("{}")
    monkeypatch.setattr(provider, "GLOBAL_SOCCER_STATS_PATH", path)
    monkeypatch.setattr(provider, "SOCCER_STATS_PATH", manual)
    assert provider.get_soccer_team_stats("Arsenal", "EPL")["games"] == 8
    assert provider.get_soccer_team_stats("Arsenal", "UEFA Champions League")["games"] == 1
    assert provider.get_soccer_team_stats("Arsenal", "La Liga") is None


def test_batch_views_select_competition_and_guard_still_refuses_thin_samples(tmp_path, monkeypatch):
    import run_soccer_batch as batch
    from data_guard import guard_teams
    store = merge_records({"France": record("UEFA Nations League", games=3)}, {})
    (tmp_path / "data").mkdir()
    (tmp_path / "data/soccer_stats.json").write_text(json.dumps(store))
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    teams = batch.load_all_soccer_teams("UEFA Nations League")
    assert teams["France"]["games"] == 3
    assert guard_teams(teams, "soccer", ["France"])[0] is False
    assert batch.load_all_soccer_teams("Premier League") == {}
