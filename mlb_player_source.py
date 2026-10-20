"""Official MLB player metrics; join measured Savant wOBA by MLB player ID."""
import csv
import datetime as dt
import io
import math
from collections import Counter

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = 'https://statsapi.mlb.com/api/v1/stats'
SAVANT = 'https://baseballsavant.mlb.com/leaderboard/expected_statistics'


def session():
    client = requests.Session()
    client.mount('https://', HTTPAdapter(max_retries=Retry(
        total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['GET'], respect_retry_after_header=True)))
    return client


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def splits(payload, season, group):
    blocks = [x for x in payload.get('stats', []) if x.get('group', {}).get('displayName') == group]
    if len(blocks) != 1:
        raise ValueError(f'MLB {group} response group missing or ambiguous')
    block = blocks[0]
    rows = block.get('splits', [])
    if not rows or block.get('totalSplits') != len(rows):
        raise ValueError(f'MLB {group} response empty or truncated')
    if any(str(x.get('season')) != str(season) for x in rows):
        raise ValueError('MLB response contains a different season')
    ids = [str(x['player']['id']) for x in rows]
    if len(ids) != len(set(ids)):
        # Never silently choose one club stint for a traded player.
        raise ValueError(f'MLB {group} response contains duplicate player IDs')
    return rows


def parse_metrics(pitching, hitting, savant_text, season, min_pa=50, min_ip=10):
    pitch_rows = splits(pitching, season, 'pitching')
    hit_rows = splits(hitting, season, 'hitting')
    woba = {}
    reader = csv.DictReader(io.StringIO(savant_text.lstrip('\ufeff')))
    if not {'player_id', 'year', 'woba'} <= set(reader.fieldnames or []):
        raise ValueError('Savant measured wOBA columns missing; expected wOBA is not a substitute')
    for row in reader:
        if str(row['year']) != str(season):
            raise ValueError('Savant response contains a different season')
        ident = str(row['player_id'])
        if ident in woba:
            raise ValueError('Duplicate Savant player ID')
        measured = number(row['woba'])
        if measured is not None and 0 <= measured <= 2:
            woba[ident] = measured
    pitchers = []
    hitters = []
    for row in pitch_rows:
        stat = row['stat']; person = row['player']
        outs, faced, strikeouts, era = [number(stat.get(k)) for k in ['outs', 'battersFaced', 'strikeOuts', 'era']]
        if None in (outs, faced, strikeouts, era) or outs < min_ip * 3 or faced <= 0:
            continue
        pitchers.append({'name': person['fullName'], 'player_id': person['id'],
                         'team': row.get('team', {}).get('name'), 'outs': int(outs),
                         'ip': outs / 3, 'k_per_9': strikeouts * 27 / outs,
                         'k_rate': strikeouts / faced, 'k_percent': strikeouts / faced,
                         'era': era, 'source': API})
    unmatched = 0
    for row in hit_rows:
        stat = row['stat']; person = row['player']
        pa, ab, hits, bases = [number(stat.get(k)) for k in ['plateAppearances', 'atBats', 'hits', 'totalBases']]
        if None in (pa, ab, hits, bases) or pa < min_pa or ab <= 0:
            continue
        measured = woba.get(str(person['id']))
        if measured is None:
            unmatched += 1
            continue
        hitters.append({'name': person['fullName'], 'player_id': person['id'],
                        'team': row.get('team', {}).get('name'), 'pa': int(pa),
                        'tb_per_pa': bases / pa, 'iso': (bases - hits) / ab,
                        'woba': measured, 'source': [API, SAVANT]})
    if not pitchers or not hitters:
        raise ValueError('Official sources produced no complete MLB player records')
    # Existing model lookups use names. Omit every ambiguous name rather than merge people.
    ambiguous_pitchers = {name for name, count in Counter(x['name'] for x in pitchers).items() if count > 1}
    ambiguous_hitters = {name for name, count in Counter(x['name'] for x in hitters).items() if count > 1}
    pitchers = [x for x in pitchers if x['name'] not in ambiguous_pitchers]
    hitters = [x for x in hitters if x['name'] not in ambiguous_hitters]
    if not pitchers or not hitters:
        raise ValueError('No unambiguous MLB player records')
    return {'season': season, 'updated': dt.datetime.now(dt.timezone.utc).isoformat(),
            'schema_version': 2, 'source': 'Official MLB Stats API + Baseball Savant',
            'pitchers': pitchers, 'hitters': hitters,
            'batters': {x['name']: x for x in hitters},
            'coverage': {'hitters_missing_measured_woba': unmatched,
                         'ambiguous_pitcher_names_omitted': sorted(ambiguous_pitchers),
                         'ambiguous_hitter_names_omitted': sorted(ambiguous_hitters)},
            'metric_definitions': {'k_rate': 'strikeouts / batters faced (fraction)',
                                   'iso': '(total bases - hits) / at bats',
                                   'woba': 'measured Savant woba; never est_woba',
                                   'ip': 'outs / 3; baseball .1 and .2 are not decimal innings'}}


def fetch_metrics(season, min_pa=50, min_ip=10):
    with session() as client:
        responses = []
        for group in ('pitching', 'hitting'):
            response = client.get(API, params={'stats': 'season', 'group': group,
                'season': season, 'sportIds': 1, 'playerPool': 'ALL', 'limit': 3000}, timeout=(10, 45))
            response.raise_for_status(); responses.append(response.json())
        response = client.get(SAVANT, params={'type': 'batter', 'year': season,
            'position': '', 'team': '', 'min': 0, 'csv': 'true'}, timeout=(10, 45))
        response.raise_for_status()
        return parse_metrics(*responses, response.content.decode('utf-8-sig'), season, min_pa, min_ip)
