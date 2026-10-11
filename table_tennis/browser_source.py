"""Read public MyStake DOM; never click prices or access private browser state."""
import hashlib
import re
from urllib.parse import urlsplit
from .contracts import validate_event, validate_quote, timestamp, utcnow, normalized_name

# These selectors were observed in the real sportsbook DOM, not guessed APIs.
DOM_CAPTURE = """() => ({text: document.body.innerText,
  markets: Array.from(document.querySelectorAll('.market')).map(m => ({
    title: m.querySelector('.title')?.getAttribute('title'),
    selections: Array.from(m.querySelectorAll('.odd-rect')).map(o => ({
      name: o.querySelector('.name')?.textContent?.trim(),
      price: Array.from(o.querySelectorAll('span')).filter(s => !s.classList.contains('name')).map(s => s.textContent.trim()).join(''),
      suspended: o.classList.contains('disabled') || o.getAttribute('aria-disabled') === 'true'
    }))
  }))})"""

def checked_url(url):
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname!='mystake.com' or u.query or u.fragment:
        raise ValueError('Use the MyStake outer HTTPS match URL, without tokens or query parameters')
    match=re.fullmatch(r'/us/sportsbook/prematch/match/(\d+)',u.path)
    if not match:raise ValueError('Open a specific MyStake prematch match and copy its address')
    return match[1]

def copied_lines(text):
    # Clipboard rendering can join VS/date and a selection/decimal price.
    # Split only explicit labels; retain raw text for scope checks and audit.
    lines=[]
    for raw in text.splitlines():
        line=raw.strip()
        if not line:continue
        if re.match(r'^VS(?=[A-Z])',line):
            lines.extend(['VS',line[2:]]);continue
        joined=re.fullmatch(r'((?:1|2)(?:\s*\([+-]?\d+(?:\.\d+)?\))?|(?:Over|Under)\s*\([+-]?\d+(?:\.\d+)?\))\s*(\d+\.\d+)',line)
        if joined:lines.extend(joined.groups())
        else:lines.append(line)
    return lines

def capture_from_text(text,url):
    """Fallback for copying the loaded sportsbook iframe with Ctrl+A/Ctrl+C.

    A saved file's modification time records observation time; callers must not
    relabel old copied prices as fresh by supplying a new timestamp.
    """
    checked_url(url)
    lines=copied_lines(text)
    markets=[];current=None
    titles={'2 Way','Total','Total Points','Point Handicap','Total Games','Total Sets','Set Handicap','Game Handicap'}
    for i,line in enumerate(lines):
        if line in titles or 'game - ' in line:
            current=dict(title=line,selections=[]);markets.append(current)
        elif current and re.fullmatch(r'(?:1|2|Over|Under)(?:\s*\([+-]?\d+(?:\.\d+)?\))?',line):
            if i+1<len(lines) and re.fullmatch(r'\d+\.\d+',lines[i+1]):
                current['selections'].append(dict(name=line,price=lines[i+1]))
    return dict(text=text,url=url,markets=markets)

def capture(url, headless=False):
    checked_url(url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ValueError('Install: venv/Scripts/python.exe -m pip install -r requirements-table-tennis.txt') from None
    with sync_playwright() as p:
        try:browser=p.chromium.launch(headless=headless)
        except Exception:
            raise ValueError('Browser unavailable. Run: venv/Scripts/python.exe -m playwright install chromium') from None
        try:
            page=browser.new_page()
            page.goto(url,wait_until='domcontentloaded',timeout=60000)
            frame=page.frame_locator('iframe[name="sportsbook_iframe"]')
            frame.locator('.market .title').first.wait_for(timeout=60000)
            data=frame.locator('body').evaluate('(el) => ('+DOM_CAPTURE+')()')
            data.update(url=url,captured_utc=utcnow())
            return data
        except Exception:
            raise ValueError('MyStake match DOM did not load. Check the match URL in your browser; no prices were imported.') from None
        finally:browser.close()

def parse_capture(data, match, start_utc, best_of):
    """Require verified start/format; page omits timezone, year and format."""
    eid='mystake:'+checked_url(data['url'])
    names=re.split(r'\s+vs\s+',match,flags=re.I)
    if len(names)!=2:raise ValueError('Use full names: First Player vs Second Player')
    text=data['text'];now=data['captured_utc'];start=timestamp(start_utc)
    if start<=timestamp(now):raise ValueError('Match start has passed; use a genuinely upcoming prematch fixture')
    # Page participant paragraphs are separated by VS and the displayed date.
    lines=copied_lines(text)
    try:
        vs=lines.index('VS');a=lines[vs-1];b=lines[vs+2]
    except (ValueError,IndexError):raise ValueError('Cannot identify participants in MyStake DOM') from None
    if sorted(map(normalized_name,(a,b)))!=sorted(map(normalized_name,names)):
        raise ValueError('MyStake match participants do not match the requested full names')
    if not all(x in text for x in ('Table Tennis','Czechia','Czech Liga Pro')):
        raise ValueError('Page is not verified Czech Liga Pro table tennis')
    pid=lambda n:'mystake:name_'+hashlib.sha256(' '.join(normalized_name(n)).encode()).hexdigest()[:24]
    e=validate_event(dict(event_id=eid,provider='mystake',provider_event_id=eid.split(':')[1],
        player_a=a,player_b=b,player_a_id=pid(a),player_b_id=pid(b),
        player_identity_basis='normalized full name; cross-provider IDs are not merged',
        league='Czech Liga Pro',country='CZ',start_utc=start.isoformat(),retrieved_utc=now,
        start_provenance='user-confirmed timezone-aware start',format_provenance='user-confirmed',
        displayed_start=lines[vs+1],source_url=data['url'],best_of=best_of,
        status='scheduled',game_scores=[],current_points=[0,0]))
    quotes=[];notes=[]
    titles={'2 Way':'moneyline','Total':'points_total',
        'Total Points':'points_total','Point Handicap':'points_spread',
        'Total Games':'games_total','Total Sets':'games_total','Set Handicap':'games_spread',
        '1st game - winner':'first_game_moneyline','1st game - point handicap':'first_game_spread',
        '1st game - total points':'first_game_total'}
    for m in data['markets']:
        title=m.get('title');market=titles.get(title)
        if not market:
            notes.append('Excluded ambiguous/unsupported market: '+str(title));continue
        paired={}
        for s in m['selections']:
            if s.get('suspended'):continue
            name=s.get('name','');price=s.get('price')
            if 'moneyline' in market:
                if name not in ('1','2'):continue
                line=None;side='a' if name=='1' else 'b'
            else:
                item=re.fullmatch(r'(Over|Under|1|2)\s*\(([+-]?\d+(?:\.\d+)?)\)',name)
                if not item:continue
                label,val=item.groups();line=float(val)
                if 'total' in market:
                    if label not in ('Over','Under'):continue
                    side='a' if label=='Over' else 'b'
                else:
                    if label not in ('1','2'):continue
                    side='a' if label=='1' else 'b'
                    if side=='b':line=-line
            sides=paired.setdefault(line,{})
            if side in sides:raise ValueError('Duplicate selection in a market; capture is ambiguous')
            sides[side]=price
        for line,sides in paired.items():
            if title=='Total' and line<=5:
                notes.append('Excluded Total: game/set units are ambiguous at this line');continue
            if set(sides)!= {'a','b'}:
                notes.append(f'Excluded one-sided {title} {line}');continue
            try:
                q=validate_quote(dict(event_id=eid,market=market,line=line,
                    price_a=sides['a'],price_b=sides['b'],bookmaker='MyStake',
                    quoted_utc=now,retrieved_utc=now,is_live=False,source_url=data['url'],
                    timestamp_basis='DOM observation time; upstream price age unknown',market_label=title))
            except ValueError as exc:
                notes.append(f'Excluded {title} {line}: {exc}');continue
            quotes.append(q)
    if not any(q['market']=='moneyline' for q in quotes):
        raise ValueError('No paired active moneyline; no defensible market anchor')
    notes.append('DOM capture time is known; upstream sportsbook price age is unverified.')
    return e,quotes,notes
