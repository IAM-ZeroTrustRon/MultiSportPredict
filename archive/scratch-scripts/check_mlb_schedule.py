import urllib.request, json

for date_str in ['2026-06-17', '6/17/2026']:
    try:
        url = f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read().decode()
        data = json.loads(raw)
        total = data.get('totalGames', data.get('totalItems', 0))
        print(f'Date {date_str}: totalGames={total}')
        if total > 0:
            for d in data['dates']:
                for g in d['games']:
                    away_name = g['teams']['away']['team']['name']
                    home_name = g['teams']['home']['team']['name']
                    hp = g['teams']['home'].get('probablePitcher', {}).get('fullName', 'TBD')
                    ap = g['teams']['away'].get('probablePitcher', {}).get('fullName', 'TBD')
                    print(f'  {away_name} @ {home_name} | {ap} vs {hp}')
            break
    except Exception as e:
        print(f'Date {date_str}: {e}')