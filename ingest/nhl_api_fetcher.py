"""Published NHL/MoneyPuck adapters; no browser scraping or fabricated metrics."""
import datetime as dt
from pathlib import Path

import pandas as pd

from nhl_sources import MP, download_csv, schedule, utcnow, stamp
from sports_feed import ROOT, today, atomic_json


class NHLAPIFetcher:
    def fetch_advanced_metrics(self, season=None):
        year = int(today()[:4]); month = int(today()[5:7])
        season = season if season is not None else year if month >= 7 else year-1
        url = f"{MP}/seasonSummary/{season}/regular/teams.csv"
        required = ["team", "situation", "xGoalsPercentage", "corsiPercentage", "highDangerShotsFor",
                    "highDangerShotsAgainst", "shotsOnGoalAgainst", "goalsAgainst"]
        path, metadata = download_csv(url, f"teams_{season}.csv", required)
        frame = pd.read_csv(path)
        frame = frame[frame.situation == "5on5"].copy()
        if frame.empty or frame.team.duplicated().any():
            raise ValueError("Missing/duplicate 5-on-5 team summary")
        out = frame[["team"]].copy()
        for source, field in [("xGoalsPercentage", "xg_share"), ("corsiPercentage", "corsi_share")]:
            value = pd.to_numeric(frame[source], errors="raise")
            if value.isna().any() or not value.between(0, 1).all():
                raise ValueError("MoneyPuck share must be in [0,1]")
            out[field] = value
        for col in required[4:]:
            frame[col] = pd.to_numeric(frame[col], errors="raise")
            if frame[col].isna().any() or (frame[col] < 0).any():
                raise ValueError("Invalid MoneyPuck shot/goal count")
        denom = frame.highDangerShotsFor+frame.highDangerShotsAgainst
        out["high_danger_shot_share"] = frame.highDangerShotsFor/denom.where(denom > 0)
        out["team_save_pct"] = 1-frame.goalsAgainst/frame.shotsOnGoalAgainst.where(frame.shotsOnGoalAgainst > 0)
        if (frame.goalsAgainst > frame.shotsOnGoalAgainst).any():
            raise ValueError("Goals cannot exceed shots on goal against")
        out["season_start"] = season
        out["retrieved_utc"] = metadata["retrieved_utc"]
        out["source_url"] = url
        out.attrs["source"] = metadata
        return out

    def build_raw(self, out_path=None):
        """Observation export; official IDs remain authoritative, odds stay paired."""
        from score_odds import fetch, for_fixture
        events = schedule(today())
        fixtures = [g for g in events if not g["completed"] and g["date"] == today()
                    and g["status"] in {"FUT","PRE"} and stamp(g['start_time'])>stamp(utcnow())]
        if not fixtures:
            return pd.DataFrame()
        odds = fetch("NHL")
        records = []
        summaries = {s: self.fetch_advanced_metrics(s).set_index("team") for s in {g["season_start"] for g in fixtures}}
        for game in fixtures:
            row = dict(game)
            for side in ("home", "away"):
                frame = summaries[game["season_start"]]
                if game[side+"_abbrev"] not in frame.index:
                    raise ValueError("No unique advanced summary for official team abbreviation")
                for key, value in frame.loc[game[side+"_abbrev"]].items():
                    row[side+"_"+key] = value
            pairs, note = for_fixture(odds, game)
            # One JSON-valued column retains bookmaker/line/side quote dimensions.
            import json
            row["paired_quotes"] = json.dumps(pairs)
            row["odds_note"] = note
            row["snapshot_utc"] = utcnow()
            records.append(row)
        out = pd.DataFrame(records)
        path = Path(out_path or ROOT/"data/cache/nhl_source.csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp"); out.to_csv(temp, index=False); temp.replace(path)
        return out


if __name__ == "__main__":
    result = NHLAPIFetcher().build_raw()
    print(f"NHL source snapshot: {len(result)} verified fixtures; no forecasts or bets written")
