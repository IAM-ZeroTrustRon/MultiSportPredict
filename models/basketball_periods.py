"""NBA period means only. Ratios do not supply variance or betting probabilities."""
import math

NBA_PERIOD_SHARES = {'h1': 0.495, 'q1': 0.245}


def provisional_periods(projection):
    home, away = projection['home_points'], projection['away_points']
    if any(isinstance(x, bool) or not math.isfinite(float(x)) or float(x) < 0 for x in (home, away)):
        raise ValueError('Period projections require finite nonnegative full-game team scores')
    out = {}
    for period, share in NBA_PERIOD_SHARES.items():
        # Derive totals/margins from displayed team scores, not separate scaling rules.
        h, a = round(float(home) * share, 1), round(float(away) * share, 1)
        out[period + '_projection'] = {
            'home_points': h, 'away_points': a, 'total_points': round(h + a, 1),
            'home_margin': round(h - a, 1), 'home_fair_spread': round(a - h, 1),
            'share': share, 'status': 'provisional', 'method': 'Fixed full-game scoring share; unvalidated for NBA periods',
            'probability': None, 'ev': None,
            'market_status': 'Projection only - EV unavailable; no period-specific variance model',
        }
    return out
