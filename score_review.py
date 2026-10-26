"""Shared score-runner presentation; raw probabilities/EV remain full-precision fractions."""
from models.basketball_periods import provisional_periods
from models.basketball_readiness import projection_only, PROJECTION_ONLY
from probability_signal import high_probability_lines


def percent(value, signed=False):
    return '--' if value is None else (f'{value:+.2%}' if signed else f'{value:.1%}')


def price(value):
    return '--' if value is None else f'{value:+g}'


def market_rows(result, item):
    """A/B is a storage contract: Home/Away for sides, Over/Under for totals."""
    kind, line = item['kind'], item['line']
    if kind == 'total':
        labels = [f'Over {line:g}', f'Under {line:g}']
    elif kind in ('moneyline', 'spread'):
        suffix = [f' {line:+g}', f' {-line:+g}'] if kind == 'spread' else ['', '']
        labels = [f"Home: {result['home_team']}{suffix[0]}", f"Away: {result['away_team']}{suffix[1]}"]
    else:
        raise ValueError(f'Unsupported score market: {kind}')
    return [{'market': kind.title(), 'selection': label, 'probability': item.get('prob_' + side),
             'price': item.get('price_' + side), 'ev': None if projection_only(result) else item.get('ev_' + side)}
            for label, side in zip(labels, ('a', 'b'))]


def recommendation(result, item):
    if projection_only(result):
        return result['readiness']['status']
    text = item.get('recommendation') or 'No recommendation'
    # Rendering only: preserve the stored pick tokens used by the grader.
    for token, replacement in [('HOME', f"Home: {result['home_team']}"),
                               ('AWAY', f"Away: {result['away_team']}")]:
        if text.endswith(' ' + token):
            return text[:-len(token)] + replacement
    return text


def periods(result):
    if str(result.get('league', '')).upper() != 'NBA':
        return []
    # Old immutable saved runs can gain a read-only derived display without being rewritten.
    derived = provisional_periods(result['projection'])
    return [(key, label, result.get(key + '_projection') or derived[key + '_projection'])
            for key, label in [('h1', '1ST HALF'), ('q1', '1ST QUARTER')]]


def format_review(result):
    if result.get('sport') == 'nhl':
        from nhl_review import format_review as hockey_review
        return hockey_review(result)
    p = result['projection']
    display_total = round(round(p['home_points'], 1) + round(p['away_points'], 1), 1)
    lines = [f"{result['league']} {result['game_date']} | {result['away_team']} @ {result['home_team']}",
             f"HOME: {result['home_team']} | AWAY: {result['away_team']}", '', 'FULL GAME',
             f"Projected score: {result['home_team']} {p['home_points']:.1f} | {result['away_team']} {p['away_points']:.1f} "
             f"(Total: {display_total:.1f})"]
    if (result.get('odds_source') or {}).get('note'):
        lines.append('Market source: ' + result['odds_source']['note'])
    if result.get('exploratory'):
        lines += ['', 'EXPLORATORY COHORT - excluded from the core value record',
                  'Probabilities and EV are assumption-based scenarios; no actionable value verdict.',
                  'Fixture: ' + ('verified schedule' if result.get('fixture_verified') else 'UNVERIFIED; user-supplied home/away order'),
                  'INPUT PROVENANCE']
        for side, item in result.get('input_provenance', {}).items():
            metrics = ', '.join(f'{key}={value:.2f}' for key, value in item['metrics'].items())
            lines.append(f"  {side.title()}: {item['name']} | {item['status']} | {item['games']} games | {metrics} | {item['source']}")
        for item in result.get('substitutions', []):
            value = f"{item['value']:.2f}" if isinstance(item['value'], (float, int)) else item['value']
            lines.append(f"  Assumed {item['input']}: {value} [{item['source']}] ({item['why']})")
        lines += list(result.get('notes', []))
    gate = result.get('readiness')
    if gate:
        counts = gate['season_games_played']
        lines += [gate['status'],
                  f"Season {gate['season']} games before {gate['counted_before']}: Home {counts['home']} | Away {counts['away']} | Required each: {gate['required_games']}",
                  gate['reason']]
    validation = p.get('validation') or {}
    if validation.get('games') is not None:
        rmse = validation.get('margin_rmse')
        lines.append(f"Holdout: {validation['games']} games | Margin RMSE: {rmse:.2f}" if rmse is not None
                     else f"Holdout: {validation['games']} games | Margin RMSE: unavailable")
    rows = [row for item in result['markets'] for row in market_rows(result, item)]
    width = max([len('Selection')] + [len(r['selection']) for r in rows])
    lines += ['', f"{'Market':<12} {'Selection':<{width}}  {'Odds':>7}  {'Probability':>11}  Estimated EV", '-' * (width + 58)]
    for item in result['markets']:
        for row in market_rows(result, item):
            ev = result['readiness']['status'] if projection_only(result) else percent(row['ev'], True) if row['ev'] is not None else 'Unavailable - no price'
            lines.append(f"{row['market']:<12} {row['selection']:<{width}}  {price(row['price']):>7}  "
                         f"{percent(row['probability']):>11}  {ev}")
        lines.append('  ' + recommendation(result, item) + f" | Push: {percent(item.get('push_prob'))}")
    for key, label, segment in periods(result):
        lines += ['', f"{label} - PROVISIONAL PROJECTION ({segment['share']:.1%} SHARE)",
                  f"Projected score: {result['home_team']} {segment['home_points']:.1f} | "
                  f"{result['away_team']} {segment['away_points']:.1f} (Total: {segment['total_points']:.1f})",
                  f"Model fair spread (not a bookmaker line): Home {segment['home_fair_spread']:+.1f}",
                  'Probability: -- | EV: -- | Projection only - EV unavailable',
                  'Fixed-ratio estimate; no period variance model or betting recommendation.']
        for quote in (result.get('period_market_quotes') or {}).get(key, []):
            labels = ' / '.join(f"{row['selection']} ({price(row['price'])})" for row in market_rows(result, quote))
            lines.append(f"  Bookmaker {quote['kind']}: {labels} | EV unavailable - period model not calibrated")
    # Two signals, kept visibly separate: how likely the selection is to win,
    # and whether the offered price pays for it.
    best = None
    for item in result['markets']:
        for row in market_rows(result, item):
            if row['probability'] is None:
                continue
            if best is None or row['probability'] > best[1]:
                best = (row['selection'], row['probability'], row['price'], row['ev'])
    if best is not None:
        block = high_probability_lines(*best)
        if block:
            if result.get('exploratory'):
                lines += ['', f'HIGH MODEL PROBABILITY (75%+) - EXPLORATORY SCENARIO: {best[0]} {best[1]:.1%}',
                          'Assumed inputs/uncertainty; this badge does not establish a likely winning bet.']
            else:
                lines += [''] + block
    lines.append('\nFull-game probabilities and EV are uncalibrated model estimates, not proven betting returns.')
    return '\n'.join(lines)


def card_shape(result):
    """The same labels/rounding consumed by embed_builder and direct runner sends."""
    p = result['projection']
    rows = [{'name': 'Full game - projected score', 'model':
             f"Home: {result['home_team']} {p['home_points']:.1f} | Away: {result['away_team']} {p['away_points']:.1f}",
             'inline': False}]
    if result.get('exploratory'):
        rows.append({'name': 'EXPLORATORY - assumption-based scenario',
                     'model': 'Excluded from core value record; no actionable value verdict.',
                     'extra': '\n'.join(f"{i['input']}: {i['value']} [{i['source']}]" for i in result.get('substitutions', [])),
                     'inline': False})
    gate = result.get('readiness')
    if gate:
        counts = gate['season_games_played']
        rows.append({'name': 'Current-season readiness', 'model': gate['status'],
                     'extra': f"Season {gate['season']} | Home {counts['home']} | Away {counts['away']} | Required each: {gate['required_games']}"
                              + ('\n'+'; '.join(gate['reasons']) if result.get('sport')=='nhl' else ''), 'inline': False})
    if result.get('sport')=='nhl':
        rows[0]['name']='NHL regulation goal means'
        rows[0]['model']=f"Home: {result['home_team']} {p['regulation_home']:.2f} | Away: {result['away_team']} {p['regulation_away']:.2f}"
    for item in result['markets']:
        detail = []
        for row in market_rows(result, item):
            ev = result['readiness']['status'] if projection_only(result) else percent(row['ev'], True) if row['ev'] is not None else 'Unavailable - no price'
            detail.append(f"{row['selection']}: {percent(row['probability'])} | Odds {price(row['price'])} | EV {ev}")
        rows.append({'name': 'Full game - ' + item['kind'].title(), 'model': '\n'.join(detail),
                     'pick': recommendation(result, item), 'extra': f"Push: {percent(item.get('push_prob'))}", 'inline': False})
    for key, label, segment in periods(result):
        quote_notes = []
        for quote in (result.get('period_market_quotes') or {}).get(key, []):
            if quote['kind'] == 'total':
                paired = f"Over {quote['line']:g} ({price(quote.get('price_a'))}) / Under {quote['line']:g} ({price(quote.get('price_b'))})"
            elif quote['kind'] == 'spread':
                paired = f"Home {quote['line']:+g} ({price(quote.get('price_a'))}) / Away {-quote['line']:+g} ({price(quote.get('price_b'))})"
            else:
                paired = f"Home ({price(quote.get('price_a'))}) / Away ({price(quote.get('price_b'))})"
            quote_notes.append(f"Bookmaker {quote['kind']}: {paired}")
        rows.append({'name': f"{label} - PROVISIONAL ({segment['share']:.1%} SHARE)",
                     'model': f"Home: {result['home_team']} {segment['home_points']:.1f} | "
                              f"Away: {result['away_team']} {segment['away_points']:.1f}",
                     'extra': f"Total {segment['total_points']:.1f} | Model fair Home spread {segment['home_fair_spread']:+.1f}\n"
                              'Projection only - EV unavailable; no period probabilities or betting recommendation.'
                              + ('\n' + '\n'.join(quote_notes) if quote_notes else ''), 'inline': False})
    rows = [{'market': None, 'edge': None, 'pick': None, 'extra': None, 'verdict': None, **row} for row in rows]
    note = 'Uncalibrated full-game model.'
    if str(result.get('league','')).upper() == 'NBA':note += ' NBA period shares are provisional assumptions.'
    return {'markets': rows, 'notes': ['MoneyPuck.com advanced data; non-commercial published downloads.']+result.get('notes',[]) if result.get('sport')=='nhl' else [note],
            'context': str(result.get('league') or '')}
