"""
Historical Storage Module for MultiSportPredict
================================================
Provides SQLite-based storage for predictions across all sports.
Enables tracking of prediction performance over time.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


# Database path
DB_PATH = Path("multisport_history.db")


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

    # Index for faster queries
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_sport 
        ON predictions(sport, timestamp)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_teams 
        ON predictions(home_team, away_team)
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

    Returns:
        ID of the inserted (or overwritten) row
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    game_date = raw_json.get("game_date")
    event_key = raw_json.get("event_key")
    today = datetime.now().date().isoformat()
    existing = cur.execute("""
        SELECT id FROM predictions
        WHERE sport = ? AND home_team = ? AND away_team = ? AND market_type = ?
          AND date(timestamp) = ? AND result_outcome IS NULL
        ORDER BY id DESC LIMIT 1
    """, (sport, home_team, away_team, market_type, today)).fetchone()

    if event_key:
        existing = cur.execute("SELECT id FROM predictions WHERE sport=? AND event_key=? AND result_outcome IS NULL ORDER BY id DESC LIMIT 1", (sport, event_key)).fetchone()

    if existing:
        row_id = existing[0]
        cur.execute("""
            UPDATE predictions
            SET model_value = ?, market_value = ?, edge = ?, confidence = ?,
                recommendation = ?, timestamp = ?, raw_json = ?, league = ?
            WHERE id = ?
        """, (
            model_value, market_value, edge, confidence, recommendation,
            datetime.now().isoformat(), json.dumps(raw_json), league, row_id
        ))
    else:
        cur.execute("""
            INSERT INTO predictions (
                sport, home_team, away_team, market_type,
                model_value, market_value, edge,
                confidence, recommendation, timestamp, raw_json, league
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sport, home_team, away_team, market_type,
            model_value, market_value, edge,
            confidence, recommendation,
            datetime.now().isoformat(),
            json.dumps(raw_json), league
        ))
        row_id = cur.lastrowid

    if game_date or event_key:
        cur.execute("UPDATE predictions SET game_date=COALESCE(?,game_date), event_key=COALESCE(?,event_key) WHERE id=?",
                    (game_date, event_key, row_id))
    conn.commit()
    conn.close()

    return row_id


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
