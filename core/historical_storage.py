"""
Historical Storage Module for MultiSportPredict
================================================
Provides SQLite-based storage for predictions across all sports.
Enables tracking of prediction performance over time.
"""

import hashlib
import json
import math
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


# Database path
DB_PATH = Path("multisport_history.db")


# Odds snapshots are observations, not a mutable cache. The triggers below make
# that structural: a stored quote can never be rewritten or deleted, so a
# closing price and the price a forecast actually used both survive verbatim.
def _ensure_odds_snapshots(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS odds_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            created_utc TEXT NOT NULL,
            observed_utc TEXT NOT NULL,
            quote_updated_utc TEXT,
            capture_kind TEXT NOT NULL,
            sport TEXT NOT NULL,
            league TEXT NOT NULL,
            event_key TEXT NOT NULL,
            fixture_key TEXT NOT NULL,
            source_event_id TEXT,
            game_date TEXT,
            kickoff_utc TEXT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            market_type TEXT NOT NULL,
            line REAL,
            price_a REAL NOT NULL,
            price_b REAL NOT NULL,
            bookmaker TEXT,
            source TEXT NOT NULL,
            scope TEXT,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_odds_snapshots_event
            ON odds_snapshots(event_key, market_type, observed_utc);
        CREATE INDEX IF NOT EXISTS idx_odds_snapshots_fixture
            ON odds_snapshots(fixture_key, market_type, capture_kind, observed_utc);
        CREATE INDEX IF NOT EXISTS idx_odds_snapshots_kind
            ON odds_snapshots(capture_kind, observed_utc);
        CREATE TRIGGER IF NOT EXISTS odds_snapshots_append_only_update
            BEFORE UPDATE ON odds_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'odds_snapshots is append-only: capture a new quote instead of rewriting history');
            END;
        CREATE TRIGGER IF NOT EXISTS odds_snapshots_append_only_delete
            BEFORE DELETE ON odds_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'odds_snapshots is append-only: archived quotes are never deleted');
            END;
    """)
    conn.commit()


def _backfill_cohorts(cur) -> None:
    """Tag rows written before the cohort column existed.

    Runs once, inside the migration that adds the column. Derivation is the
    same helper the live write path uses, so history and new rows agree. A row
    whose probability cannot be recovered is left NULL rather than guessed.
    """
    from probability_signal import cohort_for, picked_side_signal
    rows = cur.execute(
        "SELECT id, market_type, market_value, recommendation, raw_json "
        "FROM predictions WHERE cohort IS NULL").fetchall()
    for row_id, market_type, market_value, recommendation, raw_json in rows:
        try:
            raw = json.loads(raw_json or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(raw, dict):
            continue
        line = market_value if str(market_type).lower() in ("spread", "total") else None
        signal = picked_side_signal(market_type, raw, line=line,
                                    recommendation=recommendation)
        cohort = cohort_for(signal["probability"] if signal else None,
                            exploratory=bool(raw.get("exploratory")))
        if cohort:
            cur.execute("UPDATE predictions SET cohort = ? WHERE id = ?", (cohort, row_id))


def init_db(db_path: Optional[Path] = None) -> None:
    """
    Initialize the SQLite database with required tables.
    
    Args:
        db_path: Optional custom database path
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    # Main predictions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            market_type TEXT NOT NULL,
            model_value REAL,
            market_value REAL,
            edge REAL,
            confidence REAL,
            recommendation TEXT,
            timestamp TEXT NOT NULL,
            raw_json TEXT,
            result_outcome TEXT,
            profit_loss REAL DEFAULT 0.0
        )
    """)

    # league wasn't part of the original table; add it if this db predates it.
    existing_columns = {row[1] for row in cur.execute("PRAGMA table_info(predictions)")}
    if "league" not in existing_columns:
        cur.execute("ALTER TABLE predictions ADD COLUMN league TEXT")

    for name in ("game_date", "event_key"):
        if name not in existing_columns:
            cur.execute(f"ALTER TABLE predictions ADD COLUMN {name} TEXT")

    # Dynamic position sizing (fraction of bankroll). Rows stored before this
    # column existed keep NULL and are reported separately rather than being
    # retro-fitted to a stake they never had.
    if "stake_size" not in existing_columns:
        cur.execute("ALTER TABLE predictions ADD COLUMN stake_size REAL")

    # Explicit quarantine marker complements cohort and remains queryable without JSON.
    if "is_exploratory" not in existing_columns:
        cur.execute("ALTER TABLE predictions ADD COLUMN is_exploratory INTEGER NOT NULL DEFAULT 0")
        if "cohort" in existing_columns:
            cur.execute("UPDATE predictions SET is_exploratory=1 WHERE cohort='EXPLORATORY'")

    # Observation cohorts. HIGH_PROBABILITY marks a selection the model gives
    # at least 75% to win, whether or not it is a value bet -- that record is
    # graded and reported separately from the value ledger. EXPLORATORY marks a
    # forecast built from disclosed league baselines rather than verified team
    # data, so it can never be pooled with sourced forecasts.
    if "cohort" not in existing_columns:
        cur.execute("ALTER TABLE predictions ADD COLUMN cohort TEXT")
        _backfill_cohorts(cur)
    cur.execute("UPDATE predictions SET is_exploratory=1 WHERE cohort='EXPLORATORY' AND is_exploratory=0")

    # Grading columns. They exist in the long-lived database because they were added
    # by hand before this schema was written down, which meant any fresh database
    # failed every grade with "no such column: actual_home_score". Declared here so
    # init_db() produces a schema the grader can actually write to.
    for name, ddl in (("pick", "TEXT"), ("actual_home_score", "REAL"),
                      ("actual_away_score", "REAL"), ("graded_at", "TEXT"),
                      ("grade_note", "TEXT")):
        if name not in existing_columns:
            cur.execute(f"ALTER TABLE predictions ADD COLUMN {name} {ddl}")

    _ensure_odds_snapshots(conn)

    # Index for faster queries
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_sport 
        ON predictions(sport, timestamp)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_teams 
        ON predictions(home_team, away_team)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_cohort
        ON predictions(cohort, sport, game_date)
    """)
    
    conn.commit()
    conn.close()


def store_prediction(
    sport: str,
    home_team: str,
    away_team: str,
    market_type: str,
    model_value: float,
    market_value: float,
    edge: float,
    confidence: float,
    recommendation: str,
    raw_json: Dict[str, Any],
    db_path: Optional[Path] = None,
    league: Optional[str] = None,
    stake_size: Optional[float] = None,
) -> int:
    """
    Store a prediction in the database.

    If an identical (sport, home_team, away_team, market_type) prediction was
    already logged today and hasn't been graded yet, this overwrites that row
    instead of inserting a new one -- re-running the same matchup (a common
    thing to do while testing, or to refresh with a new line) used to log a
    duplicate every time, which inflates the game count and skews the win rate
    once grading runs.

    Args:
        sport: Sport type (basketball, soccer, mlb)
        home_team: Home team name
        away_team: Away team name
        market_type: Type of market (spread, total, moneyline, props)
        model_value: Model's projected value
        market_value: Market line/value
        edge: Difference between model and market
        confidence: Confidence score (0-100)
        recommendation: Bet recommendation (STRONG BET, BET, PASS)
        raw_json: Full prediction result dictionary
        db_path: Optional custom database path
        league: Optional league/competition (e.g. "MLB", "KBO", "EPL")
        stake_size: Optional quarter-Kelly fraction of bankroll for the pick

    Returns:
        ID of the inserted (or overwritten) row
    """
    path = db_path or DB_PATH
    if stake_size is not None:
        if isinstance(stake_size, bool):
            raise ValueError("stake_size must be a fraction of bankroll, not a boolean")
        stake_size = float(stake_size)
        if not math.isfinite(stake_size) or not 0 <= stake_size <= 1:
            raise ValueError("stake_size must be a finite fraction of bankroll in [0, 1]")
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    import os
    raw_json = dict(raw_json)
    if os.environ.get("MSP_RUN_ID"):
        raw_json["_workflow_run_id"] = os.environ["MSP_RUN_ID"]
    game_date = raw_json.get("game_date")
    event_key = raw_json.get("event_key")
    fixture = raw_json.get("fixture") or {}
    fixture_id = fixture.get("game_id") or fixture.get("game_pk")
    if not event_key and fixture_id:
        event_key = f"{sport}:{fixture_id}:{market_type}"
        raw_json["event_key"] = event_key
    # Cohort tag, derived once at write time from the row's own probability.
    # Kept in the table (not recomputed on read) so a later model reset cannot
    # silently reclassify history that was already graded.
    from probability_signal import cohort_for, picked_side_signal
    line = market_value if str(market_type).lower() in ("spread", "total") else None
    exploratory = bool(raw_json.get("exploratory")) or \
        str(raw_json.get("mode", "")).lower() == "exploratory"
    side_signal = picked_side_signal(market_type, raw_json, line=line,
                                     recommendation=recommendation)
    cohort = cohort_for(side_signal["probability"] if side_signal else None,
                        exploratory=exploratory)

    today = datetime.now().date().isoformat()
    existing = cur.execute("""
        SELECT id FROM predictions
        WHERE sport = ? AND home_team = ? AND away_team = ? AND market_type = ?
          AND date(timestamp) = ? AND result_outcome IS NULL
          AND (? IS NULL OR game_date = ?)
          AND is_exploratory = ?
        ORDER BY id DESC LIMIT 1
    """, (sport, home_team, away_team, market_type, today, game_date, game_date, int(exploratory))).fetchone()

    if event_key:
        existing = cur.execute("SELECT id FROM predictions WHERE sport=? AND event_key=? AND is_exploratory=? AND result_outcome IS NULL ORDER BY id DESC LIMIT 1", (sport, event_key, int(exploratory))).fetchone()

    # Observation and production rows must never overwrite one another, even
    # when event IDs/markets match. Separate quarantine identity at write time.
    if existing:
        previous_exploratory = cur.execute("SELECT is_exploratory FROM predictions WHERE id=?", (existing[0],)).fetchone()[0]
        if bool(previous_exploratory) != exploratory:
            existing = None
    if existing:
        row_id = existing[0]
        cur.execute("""
            UPDATE predictions
            SET model_value = ?, market_value = ?, edge = ?, confidence = ?,
                recommendation = ?, timestamp = ?, raw_json = ?, league = ?, stake_size = ?,
                cohort = ?
            WHERE id = ?
        """, (
            model_value, market_value, edge, confidence, recommendation,
            datetime.now().isoformat(), json.dumps(raw_json), league, stake_size,
            cohort, row_id
        ))
    else:
        cur.execute("""
            INSERT INTO predictions (
                sport, home_team, away_team, market_type,
                model_value, market_value, edge,
                confidence, recommendation, timestamp, raw_json, league, stake_size,
                cohort
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sport, home_team, away_team, market_type,
            model_value, market_value, edge,
            confidence, recommendation,
            datetime.now().isoformat(),
            json.dumps(raw_json), league, stake_size, cohort
        ))
        row_id = cur.lastrowid

    cur.execute("UPDATE predictions SET is_exploratory=? WHERE id=?", (int(exploratory), row_id))
    if game_date or event_key:
        cur.execute("UPDATE predictions SET game_date=COALESCE(?,game_date), event_key=COALESCE(?,event_key) WHERE id=?",
                    (game_date, event_key, row_id))
    conn.commit()
    conn.close()

    return row_id


# ---------------------------------------------------------------------------
# Immutable odds snapshots
# ---------------------------------------------------------------------------
CAPTURE_KINDS = ("prediction", "closing")


def odds_fixture_key(league, game_date, home_team, away_team) -> str:
    """Provider-independent fixture key used to pair a forecast with its close."""
    def fold(text):
        normalized = unicodedata.normalize("NFKD", str(text or ""))
        return "".join(c for c in normalized.casefold() if c.isalnum())
    return f"{str(league or '').upper()}:{game_date or ''}:{fold(home_team)}:{fold(away_team)}"


def _snapshot_stamp(value, field):
    """Timezone-aware UTC timestamp or None. Naive times are refused, not guessed."""
    if value is None:
        return None
    if isinstance(value, datetime):
        stamp = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{field} must be an ISO-8601 timestamp")
    if stamp.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return stamp.astimezone(timezone.utc)


def _snapshot_price(value, field) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} is required American odds")
    price = float(value)
    if not math.isfinite(price) or abs(price) < 100:
        raise ValueError(f"{field} must be American odds of at least 100 in magnitude")
    return price


def _snapshot_line(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("line must be numeric or null")
    line = float(value)
    if not math.isfinite(line):
        raise ValueError("line must be finite")
    return line


def save_odds_snapshot(quote: Dict[str, Any], db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Append one observed price pair. Existing rows are never overwritten.

    A closing capture is refused unless the kickoff is verified and both the
    observation and the bookmaker's own quote timestamp are strictly earlier.
    That guard lives here, at the storage boundary, so no caller can archive an
    in-play price as a closing line.

    Returns {"snapshot_id", "inserted", "event_key", "fixture_key", "capture_kind"}.
    """
    if not isinstance(quote, dict):
        raise ValueError("Odds snapshot must be an object")
    capture_kind = quote.get("capture_kind")
    if capture_kind not in CAPTURE_KINDS:
        raise ValueError("capture_kind must be one of " + ", ".join(CAPTURE_KINDS))
    for field in ("sport", "league", "event_key", "home_team", "away_team", "market_type"):
        if not str(quote.get(field) or "").strip():
            raise ValueError(f"{field} is required for an odds snapshot")

    observed = _snapshot_stamp(quote.get("observed_utc"), "observed_utc") or datetime.now(timezone.utc)
    kickoff = _snapshot_stamp(quote.get("kickoff_utc"), "kickoff_utc")
    quote_updated = _snapshot_stamp(quote.get("quote_updated_utc"), "quote_updated_utc")
    price_a = _snapshot_price(quote.get("price_a"), "price_a")
    price_b = _snapshot_price(quote.get("price_b"), "price_b")
    line = _snapshot_line(quote.get("line"))

    if kickoff is None:
        raise ValueError("All prematch snapshots require the verified kickoff time")
    if capture_kind == "closing":
        if quote_updated is None:
            raise ValueError("Closing quotes require a bookmaker update timestamp")
        for field in ("bookmaker", "source_event_id", "scope"):
            if not str(quote.get(field) or "").strip():
                raise ValueError(f"Closing quotes require verified {field}")
    if kickoff is not None:
        if observed >= kickoff:
            raise ValueError("Refused in-play odds: observed at or after kickoff")
        if quote_updated is not None and quote_updated >= kickoff:
            raise ValueError("Refused in-play odds: bookmaker quote published at or after kickoff")
    if quote_updated is not None and (quote_updated-observed).total_seconds() > 5:
        raise ValueError("Bookmaker quote timestamp is in the future relative to capture")

    sport = str(quote["sport"]).strip().lower()
    league = str(quote["league"]).strip().upper()
    event_key = str(quote["event_key"]).strip()
    market_type = str(quote["market_type"]).strip()
    home_team = str(quote["home_team"]).strip()
    away_team = str(quote["away_team"]).strip()
    game_date = None if quote.get("game_date") is None else str(quote["game_date"])
    bookmaker = None if quote.get("bookmaker") is None else str(quote["bookmaker"])
    source_event_id = None if quote.get("source_event_id") is None else str(quote["source_event_id"])
    scope = None if quote.get("scope") is None else str(quote["scope"])
    source = str(quote.get("source") or ("odds_api" if bookmaker or source_event_id else "manual"))
    payload = quote.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    fixture_key = odds_fixture_key(league, game_date, home_team, away_team)

    # The same bookmaker publication collected twice is one closing observation.
    # Prediction captures are scoped to their immutable run, never a later rerun.
    identity = {"event_key": event_key, "fixture_key": fixture_key,
                "sport": sport, "league": league, "market_type": market_type, "line": line,
                "capture_kind": capture_kind, "bookmaker": bookmaker,
                "source_event_id": source_event_id, "scope": scope,
                "kickoff_utc": kickoff.isoformat(),
                "period": payload.get("period", "full_game"),
                "price_a": price_a, "price_b": price_b,
                "quote_updated_utc": quote_updated.isoformat() if quote_updated else None,
                "run_id": payload.get("run_id"),
                "observed_utc": None if capture_kind == "closing" or payload.get("run_id") else observed.isoformat()}
    snapshot_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()

    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    try:
        _ensure_odds_snapshots(conn)
        cur = conn.execute("""
            INSERT OR IGNORE INTO odds_snapshots (
                snapshot_id, created_utc, observed_utc, quote_updated_utc, capture_kind,
                sport, league, event_key, fixture_key, source_event_id, game_date,
                kickoff_utc, home_team, away_team, market_type, line, price_a, price_b,
                bookmaker, source, scope, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
            observed.isoformat(timespec="seconds"),
            None if quote_updated is None else quote_updated.isoformat(timespec="seconds"),
            capture_kind, sport, league, event_key, fixture_key, source_event_id, game_date,
            None if kickoff is None else kickoff.isoformat(timespec="seconds"),
            home_team, away_team, market_type, line, price_a, price_b,
            bookmaker, source, scope,
            json.dumps(payload, sort_keys=True, allow_nan=False, default=str)
        ))
        inserted = cur.rowcount == 1
        conn.commit()
    finally:
        conn.close()

    return {"snapshot_id": snapshot_id, "inserted": inserted, "event_key": event_key,
            "fixture_key": fixture_key, "capture_kind": capture_kind}


def capture_prediction_odds(result: Dict[str, Any], db_path: Optional[Path] = None,
                            observed_utc=None) -> Dict[str, Any]:
    """Archive the exact price pairs a persisted forecast used.

    Called by the score runners after a forecast is stored. Markets without a
    complete price pair are skipped rather than priced by assumption, and a
    quote that fails the kickoff guard is reported in `refused` instead of
    being written or silently dropped.
    """
    if not isinstance(result, dict):
        raise ValueError("Prediction capture requires the forecast result object")
    markets = result.get("markets")
    saved, refused = [], []
    import os
    run_id = os.environ.get("MSP_RUN_ID") or result.get("_workflow_run_id") or result.get("_odds_capture_run_id")
    if not isinstance(markets, list):
        return {"saved": saved, "refused": refused, "skipped_without_price": 0}

    league = result.get("league")
    sport = result.get("sport")
    game_id = result.get("game_id")
    game_date = result.get("game_date")
    fixture = result.get("fixture") if isinstance(result.get("fixture"), dict) else {}
    kickoff = next((fixture.get(key) for key in
                    ("start_time", "start_utc", "commence_time", "kickoff_utc")
                    if fixture.get(key)), None)
    settlement = result.get("settlement") if isinstance(result.get("settlement"), dict) else {}
    settlement_scope = settlement.get("scope")
    specs = {}
    odds_source = result.get("odds_source")
    if isinstance(odds_source, dict):
        for spec in odds_source.get("markets") or []:
            if isinstance(spec, dict):
                try:
                    specs[(spec.get("kind"), _snapshot_line(spec.get("line")))] = spec
                except ValueError:
                    continue

    skipped = 0
    for market in markets:
        if not isinstance(market, dict):
            continue
        kind = market.get("kind")
        try:
            line = _snapshot_line(market.get("line"))
        except ValueError:
            refused.append({"event_key": None, "reason": "line is not numeric"})
            continue
        if market.get("price_a") is None or market.get("price_b") is None:
            skipped += 1
            continue
        quote = market.get("quote") if isinstance(market.get("quote"), dict) else {}
        spec = specs.get((kind, line)) or quote
        event_key = f"{league}:{game_id}:{kind}:{line}"
        try:
            saved.append(save_odds_snapshot({
                "capture_kind": "prediction", "sport": sport, "league": league,
                "event_key": event_key, "source_event_id": spec.get("source_event_id"),
                "game_date": game_date, "kickoff_utc": kickoff,
                "home_team": result.get("home_team"), "away_team": result.get("away_team"),
                "market_type": kind, "line": line,
                "price_a": market.get("price_a"), "price_b": market.get("price_b"),
                "bookmaker": spec.get("bookmaker"), "observed_utc": observed_utc,
                "quote_updated_utc": spec.get("updated"),
                "scope": spec.get("scope") or settlement_scope,
                "payload": {"quote": spec, "market": market,
                            "run_id": run_id,
                            "run_id_basis": "direct_forecast" if str(run_id).startswith("direct_") else "workflow" if run_id else "unavailable",
                            "official_fixture_id": str(game_id) if game_id is not None else None,
                            "period": spec.get("period") or "full_game", "odds_format": "american",
                            "selection_a": "Over" if kind == "total" else result.get("home_team"),
                            "selection_b": "Under" if kind == "total" else result.get("away_team"),
                            "odds_source": odds_source.get("note") if isinstance(odds_source, dict) else None},
            }, db_path))
        except ValueError as exc:
            refused.append({"event_key": event_key, "reason": str(exc)})
    return {"saved": saved, "refused": refused, "skipped_without_price": skipped}


def get_odds_snapshots(db_path: Optional[Path] = None, *, event_key=None, fixture_key=None,
                       sport=None, capture_kind=None, market_type=None) -> List[Dict[str, Any]]:
    """Read archived quotes oldest first. Never creates a missing database."""
    path = Path(db_path or DB_PATH)
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return []
    conn.row_factory = sqlite3.Row
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='odds_snapshots'").fetchone()
        if not exists:
            return []
        query = "SELECT * FROM odds_snapshots WHERE 1=1"
        params = []
        for column, value in (("event_key", event_key), ("fixture_key", fixture_key),
                              ("sport", sport), ("capture_kind", capture_kind),
                              ("market_type", market_type)):
            if value is not None:
                query += f" AND {column} = ?"
                params.append(value)
        query += " ORDER BY observed_utc, created_utc, snapshot_id"
        rows = [dict(row) for row in conn.execute(query, params)]
    finally:
        conn.close()
    for row in rows:
        try:
            row["payload"] = json.loads(row["payload"])
        except (TypeError, ValueError):
            row["payload"] = None
    return rows


def update_prediction_outcome(
    prediction_id: int,
    outcome: str,
    profit_loss: float = 0.0,
    db_path: Optional[Path] = None
) -> None:
    """
    Update a prediction with its actual outcome.
    
    Args:
        prediction_id: ID of the prediction to update
        outcome: Result outcome (win, loss, push)
        profit_loss: Profit/loss amount
        db_path: Optional custom database path
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE predictions 
        SET result_outcome = ?, profit_loss = ?
        WHERE id = ?
    """, (outcome, profit_loss, prediction_id))
    
    conn.commit()
    conn.close()


def get_predictions(
    sport: Optional[str] = None,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    market_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    recommendation_filter: Optional[str] = None,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Query predictions with optional filters.
    
    Args:
        sport: Filter by sport type
        home_team: Filter by home team
        away_team: Filter by away team
        market_type: Filter by market type
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        recommendation_filter: Filter by recommendation type
        db_path: Optional custom database path
        
    Returns:
        DataFrame with matching predictions
    """
    path = db_path or DB_PATH
    
    query = "SELECT * FROM predictions WHERE 1=1"
    params = []
    
    if sport:
        query += " AND sport = ?"
        params.append(sport)
    if home_team:
        query += " AND home_team = ?"
        params.append(home_team)
    if away_team:
        query += " AND away_team = ?"
        params.append(away_team)
    if market_type:
        query += " AND market_type = ?"
        params.append(market_type)
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
    if recommendation_filter:
        query += " AND recommendation = ?"
        params.append(recommendation_filter)
    
    query += " ORDER BY timestamp DESC"
    
    conn = sqlite3.connect(path)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Parse raw_json column
    if not df.empty and 'raw_json' in df.columns:
        df['raw_json_parsed'] = df['raw_json'].apply(
            lambda x: json.loads(x) if x else None
        )
    
    return df


def get_prediction_summary(
    sport: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Get summary statistics for predictions.
    
    Args:
        sport: Optional sport filter
        db_path: Optional custom database path
        
    Returns:
        Dictionary with summary statistics
    """
    df = get_predictions(sport=sport, db_path=db_path)
    
    if df.empty:
        return {
            "total_predictions": 0,
            "sports": {},
        }
    
    # Overall summary
    total = len(df)
    strong_bets = len(df[df["recommendation"] == "STRONG BET"])
    bets = len(df[df["recommendation"] == "BET"])
    passes = len(df[df["recommendation"] == "PASS"])
    
    avg_confidence = df["confidence"].mean()
    avg_edge = df["edge"].mean()
    
    # By sport summary
    sport_summary = {}
    for sport_name in df["sport"].unique():
        sport_df = df[df["sport"] == sport_name]
        sport_summary[sport_name] = {
            "count": len(sport_df),
            "avg_confidence": round(sport_df["confidence"].mean(), 1),
            "avg_edge": round(sport_df["edge"].mean(), 2),
            "strong_bets": len(sport_df[sport_df["recommendation"] == "STRONG BET"]),
            "bets": len(sport_df[sport_df["recommendation"] == "BET"]),
        }
    
    # By market type summary
    market_summary = {}
    for market in df["market_type"].unique():
        market_df = df[df["market_type"] == market]
        market_summary[market] = {
            "count": len(market_df),
            "avg_confidence": round(market_df["confidence"].mean(), 1),
            "avg_edge": round(market_df["edge"].mean(), 2),
        }
    
    return {
        "total_predictions": total,
        "strong_bets": strong_bets,
        "bets": bets,
        "passes": passes,
        "avg_confidence": round(avg_confidence, 1),
        "avg_edge": round(avg_edge, 2),
        "by_sport": sport_summary,
        "by_market": market_summary,
        "date_range": {
            "earliest": df["timestamp"].min(),
            "latest": df["timestamp"].max()
        }
    }


def export_predictions_to_json(
    output_path: Path,
    sport: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    Export predictions to a JSON file.
    
    Args:
        output_path: Path to output JSON file
        sport: Optional sport filter
        db_path: Optional custom database path
    """
    df = get_predictions(sport=sport, db_path=db_path)
    
    # Convert to list of dicts, excluding raw_json (use parsed version)
    records = df.to_dict('records')
    for record in records:
        if 'raw_json_parsed' in record:
            record['raw_json'] = record.pop('raw_json_parsed')
        elif 'raw_json' in record:
            try:
                record['raw_json'] = json.loads(record['raw_json'])
            except:
                record['raw_json'] = None
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(records, f, indent=2, default=str)


def get_recent_predictions(
    limit: int = 10,
    sport: Optional[str] = None,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Get most recent predictions.
    
    Args:
        limit: Number of predictions to return
        sport: Optional sport filter
        db_path: Optional custom database path
        
    Returns:
        DataFrame with most recent predictions
    """
    df = get_predictions(sport=sport, db_path=db_path)
    return df.head(limit)


def delete_old_predictions(
    days_old: int = 365,
    db_path: Optional[Path] = None
) -> int:
    """
    Delete predictions older than specified days.
    
    Args:
        days_old: Delete predictions older than this many days
        db_path: Optional custom database path
        
    Returns:
        Number of deleted records
    """
    from datetime import timedelta
    
    path = db_path or DB_PATH
    cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
    
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM predictions 
        WHERE timestamp < ?
    """, (cutoff_date,))
    
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    
    return deleted


def table_tennis_win_cover_gap(records, min_matches=20, gap_pp=15.0):
    """Compare win/point-cover rates on the SAME settled matches.

    Each record has match_won (bool), point_margin and the player's signed
    point_handicap. Pushes are excluded from both denominators. This is a
    descriptive screening flag, not a test that the rates should be equal.
    """
    from table_tennis.contracts import number
    if isinstance(min_matches, bool) or not isinstance(min_matches,int) or min_matches<1:
        raise ValueError('min_matches must be a positive integer')
    gap_pp=number(gap_pp)
    if not 0<gap_pp<=100:raise ValueError('gap_pp must be in (0, 100]')
    records=list(records)
    wins=covers=pushes=won_no_cover=lost_cover=0
    for r in records:
        if not isinstance(r.get('match_won'),bool):raise ValueError('match_won must be boolean')
        margin=number(r['point_margin']);line=number(r['point_handicap'])
        if margin!=int(margin) or line*2!=round(line*2):raise ValueError('Integer point margin and integer/half handicap required')
        settled=margin+line
        if settled==0:pushes+=1;continue
        won=r['match_won'];covered=settled>0
        wins+=won;covers+=covered
        won_no_cover+=won and not covered;lost_cover+=not won and covered
    n=len(records)-pushes
    wr=wins/n if n else None;cr=covers/n if n else None
    gap=(wr-cr)*100 if n else None
    enough=n>=min_matches
    return dict(matches=len(records),settled_matches=n,pushes=pushes,
        match_wins=wins,point_covers=covers,match_win_percentage=wr*100 if n else None,
        point_cover_percentage=cr*100 if n else None,gap_percentage_points=gap,
        won_without_cover=won_no_cover,lost_but_covered=lost_cover,
        flagged=enough and abs(gap)>=gap_pp,
        status='DESCRIPTIVE GAP' if enough and abs(gap)>=gap_pp else ('NO LARGE GAP' if enough else 'INSUFFICIENT MATCHED HISTORY'),
        minimum_matches=min_matches,threshold_percentage_points=gap_pp,
        interpretation='Win and cover rates need not be equal. This is not EV or proof of mispricing.')


class TableTennisStore:
    """Czech-only collection in the canonical database, isolated from bet rows.

    Results, source corrections, quotes and immutable forecasts are retained
    separately so collecting/training never invents bets in the main ledger.
    """
    def __init__(self, db_path=None):
        self.path = Path(db_path) if db_path is not None else Path(__file__).resolve().parents[1] / 'multisport_history.db'
        if str(self.path).startswith('\\\\'):
            raise ValueError('Database writes require a local disk')
        with self._connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS tt_events (
                    event_id TEXT PRIMARY KEY, start_utc TEXT NOT NULL,
                    status TEXT NOT NULL, player_a_id TEXT NOT NULL,
                    player_b_id TEXT NOT NULL, payload TEXT NOT NULL,
                    version INTEGER NOT NULL, updated_utc TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS tt_events_start ON tt_events(start_utc,status);
                CREATE TABLE IF NOT EXISTS tt_event_versions (
                    event_id TEXT NOT NULL, version INTEGER NOT NULL,
                    received_utc TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(event_id,version));
                CREATE TABLE IF NOT EXISTS tt_quotes (
                    quote_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
                    quoted_utc TEXT NOT NULL, market TEXT NOT NULL,
                    payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS tt_quotes_event ON tt_quotes(event_id,quoted_utc);
                CREATE TABLE IF NOT EXISTS tt_runs (
                    run_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
                    created_utc TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS tt_runs_event ON tt_runs(event_id,created_utc);
                CREATE TABLE IF NOT EXISTS tt_grades (
                    run_id TEXT NOT NULL, selection_id TEXT NOT NULL,
                    event_version INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(run_id,selection_id));
            ''')

    def _connection(self):
        # sqlite's context manager commits but does not close; explicitly close.
        from contextlib import contextmanager
        @contextmanager
        def opened():
            conn = sqlite3.connect(str(self.path), timeout=30)
            try:
                with conn:
                    yield conn
            finally:
                conn.close()
        return opened()

    def upsert_event(self, event):
        from table_tennis.contracts import validate_event
        event = validate_event(event)
        raw = json.dumps(event, sort_keys=True, allow_nan=False)
        with self._connection() as conn:
            row = conn.execute('SELECT payload,version FROM tt_events WHERE event_id=?', (event['event_id'],)).fetchone()
            version = 1
            if row:
                old = json.loads(row[0])
                if (old['player_a_id'], old['player_b_id']) != (event['player_a_id'], event['player_b_id']):
                    raise ValueError('Provider event changed player identity; explicit reconciliation required')
                comparable = lambda x: {k:v for k,v in x.items() if k != 'retrieved_utc'}
                if comparable(old) == comparable(event):
                    conn.execute('UPDATE tt_events SET updated_utc=? WHERE event_id=?', (event['retrieved_utc'],event['event_id']))
                    return 'duplicate'
                version = row[1]+1
            conn.execute('INSERT INTO tt_event_versions VALUES(?,?,?,?)', (event['event_id'],version,event['retrieved_utc'],raw))
            conn.execute('INSERT OR REPLACE INTO tt_events VALUES(?,?,?,?,?,?,?,?)',
                         (event['event_id'],event['start_utc'],event['status'],event['player_a_id'],event['player_b_id'],raw,version,event['retrieved_utc']))
        return 'corrected' if row else 'inserted'

    def event(self, event_id):
        with self._connection() as conn:
            row = conn.execute('SELECT payload,version FROM tt_events WHERE event_id=?',(event_id,)).fetchone()
        if not row:
            raise ValueError('Event is not in the Czech store; refresh or import a verified event')
        out = json.loads(row[0]);out['store_version']=row[1]
        return out

    def events(self, finished_only=False):
        with self._connection() as conn:
            query = 'SELECT payload,version FROM tt_events'
            if finished_only:query += " WHERE status='finished'"
            query += ' ORDER BY start_utc,event_id'
            rows=conn.execute(query).fetchall()
        return [dict(json.loads(r[0]),store_version=r[1]) for r in rows]

    def add_quote(self, quote):
        import hashlib
        from table_tennis.contracts import validate_quote
        q=validate_quote(quote)
        self.event(q['event_id'])
        identity={k:v for k,v in q.items() if k!='retrieved_utc'}
        key=hashlib.sha256(json.dumps(identity,sort_keys=True,allow_nan=False).encode()).hexdigest()
        with self._connection() as conn:
            conn.execute('INSERT OR IGNORE INTO tt_quotes VALUES(?,?,?,?,?)',
                         (key,q['event_id'],q['quoted_utc'],q['market'],json.dumps(q,allow_nan=False)))
        return key

    def quotes(self, event_id):
        with self._connection() as conn:
            rows=conn.execute('SELECT payload FROM tt_quotes WHERE event_id=? ORDER BY quoted_utc DESC',(event_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def quotes_by_event(self):
        grouped = {}
        with self._connection() as conn:
            for event_id, raw in conn.execute('SELECT event_id,payload FROM tt_quotes ORDER BY quoted_utc DESC'):
                grouped.setdefault(event_id, []).append(json.loads(raw))
        return grouped

    def player_point_cover_gap(self, player_id, point_handicap, bookmaker, as_of=None,
                               min_matches=20, gap_pp=15.0, limit=100):
        """One closing prematch quote per event at this exact player handicap.

        Alternative lines and repeated captures are never independent samples.
        Unknown quote freshness and missing point results are not substituted.
        """
        from table_tennis.contracts import timestamp,utcnow,number
        from datetime import timedelta
        line=number(point_handicap);cutoff=timestamp(as_of or utcnow())
        if line*2!=round(line*2):raise ValueError('Use an integer or half point handicap')
        if not bookmaker:raise ValueError('A single bookmaker is required')
        if isinstance(limit,bool) or not isinstance(limit,int) or limit<1:raise ValueError('limit must be a positive integer')
        # Restrict player/time in SQL rather than re-reading all league history.
        with self._connection() as conn:
            rows=conn.execute("""SELECT payload FROM tt_events WHERE status='finished'
                AND (player_a_id=? OR player_b_id=?) AND start_utc<?
                ORDER BY start_utc DESC,event_id""",(player_id,player_id,cutoff.isoformat())).fetchall()
        records=[]
        for row in rows:
            e=json.loads(row[0]);start=timestamp(e['start_utc'])
            available=timestamp(e['end_utc']) if e.get('end_utc') else start.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
            if available>=cutoff:continue
            side=0 if e['player_a_id']==player_id else 1
            chosen=None
            for q in self.quotes(e['event_id']):
                if q['market']!='points_spread' or q['bookmaker']!=bookmaker or q['is_live']:continue
                signed=q['line'] if side==0 else -q['line']
                if signed!=line:continue
                age=(start-timestamp(q['quoted_utc'])).total_seconds()
                if 0<age<=3600:chosen=q;break
            if chosen is None:continue
            scores=e['game_scores'];margin=sum(s[side]-s[1-side] for s in scores)
            records.append(dict(event_id=e['event_id'],match_won=sum(s[side]>s[1-side] for s in scores)==3,
                                point_margin=margin,point_handicap=line))
            if len(records)==limit:break
        result=table_tennis_win_cover_gap(records,min_matches,gap_pp)
        result.update(player_id=player_id,point_handicap=line,bookmaker=bookmaker,
                      as_of=cutoff.isoformat(),event_ids=[r['event_id'] for r in records])
        return result

    def save_run(self, report):
        import os
        if os.environ.get("MSP_RUN_ID"):
            report["_workflow_run_id"] = os.environ["MSP_RUN_ID"]
        with self._connection() as conn:
            conn.execute('INSERT INTO tt_runs VALUES(?,?,?,?)',(report['run_id'],report['event']['event_id'],report['created_utc'],json.dumps(report,allow_nan=False)))

    def run(self, run_id):
        with self._connection() as conn:
            row=conn.execute('SELECT payload FROM tt_runs WHERE run_id=?',(run_id,)).fetchone()
        if not row:raise ValueError('Saved run ID was not found')
        return json.loads(row[0])

    def runs(self):
        with self._connection() as conn:
            return [json.loads(r[0]) for r in conn.execute('SELECT payload FROM tt_runs ORDER BY created_utc')]

    def save_grade(self, run_id, selection_id, event_version, grade):
        with self._connection() as conn:
            conn.execute('INSERT OR REPLACE INTO tt_grades VALUES(?,?,?,?)',
                         (run_id,selection_id,event_version,json.dumps(grade,allow_nan=False)))

    def stats(self):
        with self._connection() as conn:
            out={t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('tt_events','tt_quotes','tt_runs','tt_grades')}
            out['finished']=conn.execute("SELECT COUNT(*) FROM tt_events WHERE status='finished'").fetchone()[0]
            out['range']=conn.execute("SELECT MIN(start_utc),MAX(start_utc) FROM tt_events WHERE status='finished'").fetchone()
        return out


# Workflow state shares the canonical database; forecasts and delivery are distinct facts.
from contextlib import contextmanager, closing


@contextmanager
def workflow_connection(db_path=None):
    path = Path(db_path or Path(__file__).resolve().parents[1] / 'multisport_history.db')
    if str(path).startswith('\\\\'):
        raise ValueError('Workflow SQLite writes require a local database path')
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS workflow_runs (
            run_id TEXT PRIMARY KEY, sport TEXT NOT NULL, created_utc TEXT NOT NULL,
            status TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workflow_deliveries (
            id INTEGER PRIMARY KEY, run_id TEXT, created_utc TEXT NOT NULL,
            status TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workflow_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    conn.commit()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def workflow_save_run(run_id, sport, status, payload, db_path=None):
    from datetime import timezone
    with workflow_connection(db_path) as conn:
        conn.execute('INSERT INTO workflow_runs VALUES(?,?,?,?,?)',
                     (run_id, sport, datetime.now(timezone.utc).isoformat(), status, json.dumps(payload)))


def workflow_delivery(run_id, status, payload, db_path=None):
    from datetime import timezone
    with workflow_connection(db_path) as conn:
        conn.execute('INSERT INTO workflow_deliveries(run_id,created_utc,status,payload) VALUES(?,?,?,?)',
                     (run_id, datetime.now(timezone.utc).isoformat(), status, json.dumps(payload)))


def workflow_set_meta(key, value, db_path=None):
    with workflow_connection(db_path) as conn:
        conn.execute('INSERT OR REPLACE INTO workflow_meta VALUES(?,?)', (key, json.dumps(value)))


def workflow_repair_dates(repairs, db_path=None):
    """Persist verified identities with an audit trail; never replace an existing grade."""
    with workflow_connection(db_path) as conn:
        for item in repairs:
            row = conn.execute('SELECT * FROM predictions WHERE id=?', (item['id'],)).fetchone()
            if row is None or row['result_outcome'] is not None:
                continue
            raw = json.loads(row['raw_json'] or '{}')
            if not isinstance(raw, dict):
                raise ValueError('Prediction payload is not an object')
            raw['_fixture_repair'] = item
            raw['game_date'] = item['date']
            raw['fixture'] = item['fixture']
            raw['event_key'] = f"{row['sport']}:{item['fixture']['game_id']}:{row['market_type']}"
            conn.execute('UPDATE predictions SET game_date=?,event_key=?,raw_json=? WHERE id=?',
                         (item['date'],raw['event_key'],json.dumps(raw),row['id']))


def workflow_backup(folder, db_path=None):
    from datetime import timezone
    path = Path(db_path or Path(__file__).resolve().parents[1] / 'multisport_history.db')
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('history_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
    with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity check failed')
    return target


def workflow_cleanup(prediction_ids, run_ids, before, folder, db_path=None):
    """Delete only approved unresolved historical selections, after a verified backup."""
    from datetime import date, timezone
    date.fromisoformat(before)
    backup = workflow_backup(folder, db_path)
    manifest = {'backup':str(backup), 'before':before, 'predictions':[], 'table_tennis_runs':[]}
    path = Path(db_path or Path(__file__).resolve().parents[1] / 'multisport_history.db')
    with closing(sqlite3.connect(path, timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN IMMEDIATE')
        for ident in prediction_ids:
            row=conn.execute('SELECT * FROM predictions WHERE id=?',(ident,)).fetchone()
            if row is None: continue
            if row['result_outcome'] is not None or not row['game_date'] or row['game_date'] >= before:
                raise ValueError(f'Refusing to delete graded/future/undated prediction {ident}')
            manifest['predictions'].append(dict(row))
        for ident in run_ids:
            row=conn.execute('SELECT r.*,e.start_utc,e.status AS event_status FROM tt_runs r JOIN tt_events e ON e.event_id=r.event_id WHERE r.run_id=?',(ident,)).fetchone()
            if row is None: continue
            start=datetime.fromisoformat(row['start_utc'].replace('Z','+00:00'))
            from zoneinfo import ZoneInfo
            if start.astimezone(ZoneInfo('America/New_York')).date().isoformat() >= before or row['event_status']=='finished' or conn.execute('SELECT 1 FROM tt_grades WHERE run_id=?',(ident,)).fetchone():
                raise ValueError(f'Refusing to delete settled/future table-tennis run {ident}')
            manifest['table_tennis_runs'].append(dict(row))
        # Materialize the exact deleted records before committing any removal.
        target=Path(folder)/('deleted_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        target.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        conn.executemany('DELETE FROM predictions WHERE id=?',[(r['id'],) for r in manifest['predictions']])
        conn.executemany('DELETE FROM tt_runs WHERE run_id=?',[(r['run_id'],) for r in manifest['table_tennis_runs']])
        conn.commit()
    return {'backup':str(backup), 'manifest':str(target), 'predictions_deleted':len(manifest['predictions']), 'table_tennis_runs_deleted':len(manifest['table_tennis_runs'])}
