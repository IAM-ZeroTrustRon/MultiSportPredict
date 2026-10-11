"""Independent regression probes; never writes production data."""
import json
import math
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'gemini'))
from models.table_tennis_scoring import TableTennisGameScorer
from run_table_tennis import resolve_market_odds, resolve_player_rating
from table_tennis.sources import OddsApiIoAdapter, BetsApiAdapter

results = []
def record(name, actual, expected, passed):
    results.append(dict(check=name, actual=actual, expected=expected, passed=passed))

scorer = TableTennisGameScorer(0.5)
dist = scorer.terminal_score_distribution_from_0_0()
expected = math.comb(11, 1) / 2**12
record('Exact 11-1 probability', dist[(11, 1)], expected,
       math.isclose(dist[(11, 1)], expected, abs_tol=1e-12))
expected = math.comb(20, 10) / 2**20 * 0.5 * 0.25
record('Legal 13-11 score probability', dist.get((13, 11), 0), expected,
       math.isclose(dist.get((13, 11), 0), expected, abs_tol=1e-12))
scorer = TableTennisGameScorer(0.6)
expected = 1 + 0.4 * 2 / (0.6**2 + 0.4**2)
actual = scorer.expected_points_from_state(11, 10)
record('Remaining points at 11-10', actual, expected,
       math.isclose(actual, expected, abs_tol=1e-12))
quotes = [dict(event_id='event1', match='Alice vs Bob',
               markets={'moneyline': {'home_odds': 2.15, 'away_odds': 1.65}})]
actual = resolve_market_odds('Bob', 'Alice', 'event1', quotes)
record('Reversed player quote orientation', list(actual[:2]), [1.65, 2.15],
       actual[:2] == (1.65, 2.15))
actual = resolve_market_odds('Alice', 'Bob', 'wrong-event', quotes)
record('Explicit different event must not match by names', bool(actual), False,
       actual is None)
actual = resolve_player_rating('Unknown Player', {})
record('Unknown player must not acquire an observed rating', actual[0], None,
       actual[0] is None)
for cls in (OddsApiIoAdapter, BetsApiAdapter):
    adapter = cls()
    adapter._api_key = 'audit-only-not-a-real-key'
    actual = adapter.fetch_fixtures()
    record(cls.__name__ + ' authenticated implementation', actual,
           'HTTP request or explicit unsupported error', False)

(root / 'audit_results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
print(f'Independent checks: {sum(r["passed"] for r in results)}/{len(results)} passed')
