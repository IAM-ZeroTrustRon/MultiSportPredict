import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_mlb


def test_kbo_schedule_filters_target_date_and_maps_away_home(monkeypatch):
    html = """
    <a id="game-line-14024" href="/games/14024-Hanwha-vs-Kiwoom-20261007"
       data-game-datetime="2026-10-07T09:30:00Z"></a>
    <a id="game-line-14029" href="/games/14029-Kia-vs-NC-20261009"
       data-game-datetime="2026-10-09T05:00:00Z"></a>
    """
    requested = {}

    class Response:
        text = html

        def raise_for_status(self):
            pass

    def get(url, **kwargs):
        requested["url"] = url
        requested.update(kwargs)
        return Response()

    monkeypatch.setattr(run_mlb.requests, "get", get)

    games = run_mlb.load_kbo_schedule("2026-10-09")

    assert requested["url"] == run_mlb.KBO_SCHEDULE_URL
    assert requested["params"] == {"start": "2026-10-09"}
    assert games == [{
        "game_date": "2026-10-09",
        "away_team": "KIA Tigers",
        "home_team": "NC Dinos",
        "status": "scheduled",
        "source": "mykbostats.com",
        "game_id": "/games/14029-Kia-vs-NC-20261009",
    }]


def test_kbo_schedule_returns_empty_for_a_date_without_games(monkeypatch):
    class Response:
        text = '<a id="game-line-14029" href="/games/14029-Kia-vs-NC-20261009"></a>'

        def raise_for_status(self):
            pass

    monkeypatch.setattr(run_mlb.requests, "get", lambda *args, **kwargs: Response())

    assert run_mlb.load_kbo_schedule("2026-10-08") == []


def test_kbo_schedule_fails_loudly_on_unrecognized_team_slug(monkeypatch):
    class Response:
        text = '<a id="game-line-1" href="/games/1-Unknown-vs-NC-20261009"></a>'

        def raise_for_status(self):
            pass

    monkeypatch.setattr(run_mlb.requests, "get", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError, match="Unrecognized KBO team"):
        run_mlb.load_kbo_schedule("2026-10-09")
