"""Progressive basketball workflow using the existing score model and ledger."""
import argparse
import datetime as dt
import math
import sys

from basketball_resolution import (SCORE_LEAGUES, canonical_league, prepare,
                                   hybrid, eligible_games, name_key)
from sports_feed import ROOT, today, atomic_json


def market_specs(args, reversed_order=False):
    specs, forwarded = [], []
    for kind in ('moneyline', 'spread', 'total'):
        for raw in getattr(args, kind) or []:
            nums = [None if x.lower() == 'none' else float(x) for x in raw]
            if any(v is not None and not math.isfinite(v) for v in nums):
                raise ValueError('Market lines and prices must be finite')
            if kind == 'moneyline':
                a, b = nums
                if reversed_order: a, b = b, a
                line, rendered = .5, [a, b]
            else:
                line, a, b = nums
                if line is None: raise ValueError('Market line cannot be None')
                if kind == 'spread' and reversed_order: line, a, b = -line, b, a
                rendered = [line, a, b]
            specs.append(dict(kind=kind, line=line, price_a=a, price_b=b))
            forwarded += ['--' + kind, *['None' if x is None else str(x) for x in rendered]]
    return specs, forwarded


def scenario_markets(result, specs):
    from models.score_ratings import market_probability, price_market
    projection = result['projection']
    margin = projection['home_points'] - projection['away_points']
    total = projection['home_points'] + projection['away_points']
    markets = []
    for spec in specs or [dict(kind='moneyline', line=.5)]:
        kind = spec['kind']
        if kind == 'moneyline':
            prob = .5 * (1 + math.erf(margin / (projection['margin_sd'] * math.sqrt(2))))
            probabilities = prob, 1 - prob, 0
        else:
            probabilities = market_probability(margin if kind == 'spread' else total,
                projection['margin_sd'] if kind == 'spread' else projection['total_sd'], spec['line'], kind == 'spread')
        item = price_market(kind, spec['line'], probabilities, spec.get('price_a'), spec.get('price_b'))
        observed_side = ('HOME' if probabilities[0] >= probabilities[1] else 'AWAY') if kind != 'total' else ('OVER' if probabilities[0] >= probabilities[1] else 'UNDER')
        item.update(pick=observed_side, stake_size=None, stake_basis='unavailable: exploratory observation',
                    recommendation='INFO - EXPLORATORY; scenario EV only, no actionable value verdict')
        markets.append(item)
    return markets


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument('--league', default='NBA')
    known, _ = probe.parse_known_args(values)
    league = canonical_league(known.league)
    if league == 'EUROLEAGUE' and '--exploratory' not in values:
        from euroleague_engine import run_cli
        return run_cli(values)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--league', default='NBA')
    p.add_argument('--match', action='append')
    p.add_argument('--home'); p.add_argument('--away')
    p.add_argument('--date', '--game-date', dest='date', default=today())
    p.add_argument('--exploratory', action='store_true', help='Allow disclosed hybrid priors if verified data remains insufficient')
    p.add_argument('--no-refresh', action='store_true', help='Use local data without public ingestion')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--store-to-db', action='store_true', help='Compatibility: storage is already the default')
    p.add_argument('--list-teams', action='store_true')
    p.add_argument('--push', nargs='+', type=int)
    p.add_argument('--odds', action='store_true')
    for kind, count in [('moneyline', 2), ('spread', 3), ('total', 3)]:
        p.add_argument('--' + kind, action='append', nargs=count)
    args = p.parse_args(values)
    try:
        dt.date.fromisoformat(args.date)
        if args.odds and any(getattr(args, k) for k in ('moneyline', 'spread', 'total')):
            raise ValueError('Choose --odds or manually priced flags for this run')
        if bool(args.home) != bool(args.away) or (args.home and args.match):
            raise ValueError('Use --match OR both --home and --away')
        matches = args.match or ([f'{args.home} vs {args.away}'] if args.home else [])
        if league not in SCORE_LEAGUES and not args.exploratory:
            raise ValueError(f'No supported source for {league}. Add --exploratory to authorize disclosed baseline inputs')
        if len(matches) > 1 and any(getattr(args, k) for k in ('moneyline', 'spread', 'total')):
            raise ValueError('Manual prices require one match per run')
        from score_odds import KEYS
        from run_ncaaf import main as score_main
        common = ['--league', league, '--date', args.date]
        if args.dry_run: common += ['--dry-run']
        if args.push:
            if args.exploratory:
                raise ValueError('Review exploratory observations locally; push is not enabled in this mode')
            return score_main('basketball', common + ['--push', *map(str, args.push)])
        if args.list_teams:
            from basketball_resolution import load_history
            data = load_history(league)
            print('\n'.join(sorted({g[s + '_team'] for g in data['games'] for s in ('home', 'away')})))
            return []
        if not matches:
            if args.exploratory: raise ValueError('--exploratory requires --match')
            from basketball_resolution import refresh_history
            if not args.no_refresh: refresh_history(league, args.date)
            return score_main('basketball', common + (['--odds'] if args.odds and league in KEYS else []))
        rows = []
        refresh = not args.no_refresh
        for match in matches:
            parts = [part.strip() for part in match.split(' vs ')]
            if len(parts) != 2: raise ValueError('Use full team names separated by " vs "')
            first, second = parts
            data, fixture, notes = prepare(league, first, second, args.date, refresh=refresh)
            if notes: refresh = False  # A local hit must not consume a later matchup's refresh.
            model_error = 'No uniquely verified scheduled fixture for these teams/date' if fixture is None else None
            if fixture:
                from models.score_ratings import ScoreRatings
                try:
                    model = ScoreRatings(eligible_games(data, min(today(), args.date)), min(today(), args.date), min_games=5)
                    model.predict(fixture['home_team'], fixture['away_team'], fixture.get('neutral_site', False))
                except ValueError as exc:
                    model_error = str(exc)
            if not data.get('updated') or (dt.date.fromisoformat(today()) - dt.date.fromisoformat(data['updated'])).days > 7:
                model_error = 'Fixture/history feed is stale or absent'
            specs, forwarded = market_specs(args, bool(fixture and name_key(first) != name_key(fixture['home_team'])))
            if model_error is None:
                print(f"Verified {league}: {fixture['away_team']} @ {fixture['home_team']} | {fixture['start_time']}")
                rows.extend(score_main('basketball', common + ['--match', f"{fixture['home_team']} vs {fixture['away_team']}"]
                                       + forwarded + (['--odds'] if args.odds and league in KEYS else []),
                                       prepared_models={min(today(), args.date): model}))
                continue
            if not args.exploratory:
                raise ValueError(f'{model_error}. Use --exploratory to authorize disclosed hybrid priors. ' + '; '.join(notes))
            result = hybrid(data, first, second, args.date, fixture, [model_error, *notes])
            if args.odds and fixture and league in KEYS:
                from score_odds import fetch, for_fixture
                specs, odds_note = for_fixture(fetch(league), fixture)
                specs = [s for s in specs if not s.get('period')]
            else:
                odds_note = 'User-supplied prices' if specs else 'No matched prices; probability observation only'
            result['markets'] = scenario_markets(result, specs)
            result['odds_source'] = dict(note=odds_note)
            from score_review import format_review
            result['formatted_review'] = format_review(result)
            print(result['formatted_review'])
            rows.append(result)
            if not args.dry_run:
                from run_ncaaf import store
                store(result)
        if not args.dry_run:
            path = ROOT / (f'data/basketball_{league.lower()}_review.json' if league in SCORE_LEAGUES
                           else 'data/basketball_exploratory_review.json')
            atomic_json(path, dict(generated=today(), rows=rows))
        return rows
    except (ValueError, KeyError) as exc:
        p.error(str(exc))
