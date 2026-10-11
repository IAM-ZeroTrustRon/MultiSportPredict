"""Public Sofascore browser results; no keys, assumed odds or default lines."""
import hashlib
import re
import time
from datetime import datetime,timezone
from urllib.parse import urljoin,urlsplit,urldefrag
from .contracts import validate_event,utcnow,timestamp

BASE='https://www.sofascore.com'
LEAGUE_PATH='/table-tennis/tournament/czech-republic/czech-liga-pro/19039'

# Observed on a real Czech Liga Pro page: numeric player profile links and a
# three-row table of per-game points. Read rendered DOM, not private app state.
DOM_CAPTURE="""() => {
 const ps=Array.from(document.querySelectorAll('a[href*="/table-tennis/player/"]'));
 let root=ps[0]?.parentElement;
 while(root && ps[1] && !root.contains(ps[1])) root=root.parentElement;
 return {text:document.body.innerText,summary:root?.innerText,
   leagueLinks:Array.from(document.querySelectorAll('a[href*="/table-tennis/tournament/"]')).map(a=>({href:a.getAttribute('href'),name:a.innerText})),
   players:ps.map(a=>({href:a.getAttribute('href'),name:a.innerText.trim(),imageName:a.querySelector('img')?.alt})),
   tables:Array.from(document.querySelectorAll('table')).map(t=>Array.from(t.querySelectorAll('tr')).map(r=>Array.from(r.querySelectorAll('td,th')).map(c=>c.innerText.trim())))};
}"""

def checked_match_url(url):
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname not in ('www.sofascore.com','sofascore.com') or u.query:
        raise ValueError('Use a public Sofascore HTTPS table-tennis match URL')
    if not re.fullmatch(r'/table-tennis/match/[a-zA-Z0-9-]+/[a-zA-Z0-9]+',u.path):
        raise ValueError('URL is not a Sofascore table-tennis match page')
    if u.fragment and not re.fullmatch(r'id:\d+',u.fragment):raise ValueError('Unrecognized match fragment')
    return url

def parse_match(data):
    if data.get('example') or data.get('is_example'):raise ValueError('Example snapshots are excluded from real history')
    url=checked_match_url(data['url']);text=data['text'];summary=data.get('summary') or ''
    links=data.get('leagueLinks') or []
    if not any(urldefrag(urlsplit(x['href']).path)[0]==LEAGUE_PATH and x['name'].strip()=='Czech Liga Pro' for x in links):
        raise ValueError('No verified Czech Liga Pro league link on this match')
    if not re.search(r'\bCzechia\b',text):raise ValueError('Czech country not verified')
    score=re.search(r'\b([0-3])\s*[-–]\s*([0-3])\s+Finished\b',summary)
    if not score:raise ValueError('Current match is not explicitly Finished with a final score')
    final=[int(x) for x in score.groups()]
    if max(final)!=3:raise ValueError('Finished result is not a best-of-five completion')
    players=[];seen=set()
    for p in data.get('players') or []:
        match=re.fullmatch(r'/table-tennis/player/[a-zA-Z0-9-]+/(\d+)',p['href'])
        if not match:raise ValueError('Stable numeric player profile ID missing')
        if match[1] in seen:continue
        name=p.get('imageName')
        if not name or name in ('logo','image') or name.strip()==p['name'].strip():name=p['name']
        if not name.strip():raise ValueError('Observed player name is missing')
        players.append(dict(id='sofascore:'+match[1],name=name.strip(),display_name=p['name'],profile_url=urljoin(BASE,p['href'])))
        seen.add(match[1])
    if len(players)!=2:raise ValueError('Exactly two unique player IDs required')
    # The About paragraph explicitly states UTC; do not infer browser timezone.
    raw=re.search(r'\bon\s+([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+at\s+(\d{1,2}:\d{2}:\d{2})\s*(AM|PM)\s+UTC',text)
    if not raw:raise ValueError('Explicit UTC start is missing; local display is not a substitute')
    start=datetime.strptime(f'{raw[1]} {raw[2]} {raw[3]}','%b %d, %Y %I:%M:%S %p').replace(tzinfo=timezone.utc).isoformat()
    candidates=[]
    for table in data.get('tables') or []:
        if len(table)!=3 or not all(re.fullmatch(r'\d+(?:st|nd|rd|th)',c,re.I) for c in table[0] if c):continue
        a,b=table[1:]
        if len(a)!=len(b):continue
        games=[];blank_seen=False
        for x,y in zip(a,b):
            if not x and not y:blank_seen=True;continue
            if blank_seen or not re.fullmatch(r'\d+',x) or not re.fullmatch(r'\d+',y):
                raise ValueError('Incomplete, noninteger or interrupted point-score row')
            games.append([int(x),int(y)])
        if games:candidates.append(games)
    if len(candidates)!=1:raise ValueError('Exactly one unambiguous game point-score table required')
    games=candidates[0];wins=[sum(a>b for a,b in games),sum(b>a for a,b in games)]
    if wins!=final:raise ValueError('Game point scores disagree with displayed final match score')
    # Pair URLs can display many rematches. IDs include both provider identities
    # and actual UTC start, so a head-to-head URL cannot overwrite another date.
    identity='|'.join([players[0]['id'],players[1]['id'],start])
    eid='sofascore:event_'+hashlib.sha256(identity.encode()).hexdigest()[:32]
    e=dict(event_id=eid,provider='sofascore',provider_event_id=urlsplit(url).fragment.removeprefix('id:') or None,
        league='Czech Liga Pro',country='CZ',best_of=5,status='finished',
        player_a=players[0]['name'],player_b=players[1]['name'],
        player_a_id=players[0]['id'],player_b_id=players[1]['id'],
        player_a_profile=players[0]['profile_url'],player_b_profile=players[1]['profile_url'],
        player_a_display_name=players[0]['display_name'],player_b_display_name=players[1]['display_name'],
        start_utc=start,retrieved_utc=data['captured_utc'],source_url=url,
        game_scores=games,current_points=[0,0],format_provenance='Observed legal final match ends at three game wins',
        start_provenance='Visible About paragraph explicitly states UTC')
    return validate_event(e)

class PublicResultsBrowser:
    def __init__(self,headless=True,timeout=45000):
        self.headless=headless;self.timeout=timeout;self.browser=None;self.runtime=None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
            self.runtime=sync_playwright().start()
            self.browser=self.runtime.chromium.launch(headless=self.headless)
            self.context=self.browser.new_context(locale='en-US',timezone_id='UTC')
            # Ads/media are unnecessary to read result tables; keep site JS/CSS.
            self.context.route('**/*',lambda route:route.abort() if route.request.resource_type in ('image','media','font') else route.continue_())
            self.page=self.context.new_page()
            return self
        except Exception:
            self.__exit__(None,None,None)
            raise ValueError('Public collector browser unavailable. Run: venv/Scripts/python.exe -m playwright install chromium') from None

    def __exit__(self,*args):
        try:
            if self.browser:self.browser.close()
        finally:
            if self.runtime:self.runtime.stop()

    def navigate(self,url):
        try:
            response=self.page.goto(url,wait_until='domcontentloaded',timeout=self.timeout)
            if response and response.status>=400:raise ValueError('Public source returned HTTP '+str(response.status))
            title=self.page.title().lower()
            if any(x in title for x in ('just a moment','access denied','captcha')):
                raise ValueError('Source access challenge; collector stops without bypassing it')
        except ValueError:raise
        except Exception:raise ValueError('Public source did not load within the timeout') from None

    def match(self,url):
        checked_match_url(url);self.navigate(url)
        try:
            self.page.locator('table').first.wait_for(timeout=self.timeout)
            data=self.page.evaluate(DOM_CAPTURE)
        except Exception:raise ValueError('No readable finished-match point table; retry later or use --snapshot-file') from None
        data.update(url=url,captured_utc=utcnow())
        return parse_match(data),data

    def day_links(self,day):
        datetime.strptime(day,'%Y-%m-%d')
        url=BASE+'/table-tennis/'+day;self.navigate(url)
        try:
            self.page.locator('a[href*="/table-tennis/tournament/czech-republic/czech-liga-pro/19039"]').first.wait_for(timeout=self.timeout)
            # Links are actual displayed event cards, with numeric #id fragments.
            rows=self.page.evaluate("""() => {
              const league=Array.from(document.querySelectorAll('a')).find(a=>a.getAttribute('href')?.startsWith('/table-tennis/tournament/czech-republic/czech-liga-pro/19039'));
              let root=league?.parentElement;
              while(root && !root.querySelector('a[href*="/table-tennis/match/"]'))root=root.parentElement;
              if(!root)return [];
              const other=Array.from(root.querySelectorAll('a[href*="/table-tennis/tournament/"]')).some(a=>!a.getAttribute('href').startsWith('/table-tennis/tournament/czech-republic/czech-liga-pro/19039'));
              if(other) return [];
              return Array.from(root.querySelectorAll('a[href*="/table-tennis/match/"]')).map(a=>({href:a.getAttribute('href'),text:a.innerText}));
            }""")
        except Exception:raise ValueError('No readable Czech league schedule for '+day) from None
        return sorted({urljoin(BASE,r['href']) for r in rows if re.search(r'\bFT\b',r['text']) and '#id:' in r['href']})

    def league_links(self):
        self.navigate(BASE+LEAGUE_PATH)
        try:
            self.page.locator('h1').filter(has_text='Czech Liga Pro').wait_for(timeout=self.timeout)
            rows=self.page.locator('a[href*="/table-tennis/match/"]').evaluate_all("els=>els.map(a=>({href:a.getAttribute('href'),text:a.innerText}))")
        except Exception:raise ValueError('No readable Czech Liga Pro results page') from None
        return sorted({urljoin(BASE,r['href']) for r in rows if re.search(r'\bFT\b',r['text']) and '#id:' in r['href']})

def collect_public(store,days=1,max_events=100,headless=True,match_urls=None,on_event=None,recent_only=False,on_progress=None):
    from datetime import timedelta
    counts={'inserted':0,'corrected':0,'duplicate':0,'rejected':0};notes=[]
    report=on_progress or (lambda message: None)
    report('Starting public browser; page loading can take up to 90 seconds per match.')
    with PublicResultsBrowser(headless) as source:
        links=set(match_urls or [])
        for url in links:checked_match_url(url)
        if not match_urls:
            today=datetime.now(timezone.utc).date()
            for offset in range(0 if recent_only else days):
                try:
                    day=(today-timedelta(days=offset)).isoformat()
                    report('Reading UTC schedule: '+day)
                    links.update(source.day_links(day))
                except ValueError as exc:
                    # Do not spend an hour probing every backfill day when the
                    # schedule is inaccessible; retain a bounded recent option.
                    notes.append(str(exc));break
                time.sleep(1)
            if not links:
                report('Reading Czech Liga Pro recent results...')
                links.update(source.league_links())
                notes.append('Using visible recent league results only, not a complete backfill.' if recent_only else 'Day schedule unavailable; using visible recent league results only, not a complete backfill.')
        report(f'Discovered {len(links)} links; checking up to {max_events}.')
        for number,url in enumerate(sorted(links)[:max_events],1):
            report(f'Checking match {number}/{min(len(links),max_events)}: {url}')
            try:
                event,raw=source.match(url)
                result=store.upsert_event(event)
                counts[result]+=1
                report(f'{result}: {event["player_a"]} vs {event["player_b"]}')
                if on_event:on_event(event,raw)
            except ValueError as exc:
                counts['rejected']+=1;notes.append(str(exc))
                report('Rejected: '+str(exc))
            time.sleep(1)
    if sum(counts[k] for k in ('inserted','corrected','duplicate'))==0:
        raise ValueError('No verified completed results collected. '+ '; '.join(sorted(set(notes)))[:1200])
    if len(links)>max_events:notes.append(f'Run limited to {max_events} of {len(links)} discovered links; collection is incomplete.')
    return counts,sorted(set(notes))
