"""Readable terminal reports and bounded Discord cards from saved forecasts."""
from .contracts import MARKETS,timestamp

LABELS={
 'moneyline':('💰','Match winner'),
 'games_total':('🔢','Match total games'),
 'games_spread':('⚖️','Game handicap'),
 'points_total':('🎯','Match total points'),
 'points_spread':('📏','Point handicap'),
 'first_game_moneyline':('🏓','First game winner'),
 'first_game_total':('🔢','First game total points'),
 'first_game_spread':('📏','First game point handicap')}

def heading(market):
    icon,title=LABELS[market]
    return f'{icon} {title}'

def selection(row):
    line=row['selection_line']
    suffix='' if line is None else f' {line:+g}' if 'spread' in row['market'] else f' {line:g}'
    return row['selection']+suffix

def priced_line(row):
    text=(f"{selection(row)} | Odds {row['price']:.2f} | "
          f"Win {row['probability']:.1%} | EV {row['ev']:+.1%}")
    if row['push_probability']:text+=f" | Push {row['push_probability']:.1%}"
    return text

def reference_line(row):
    market,line=row['market'],row['line']
    if 'total' in market:a,b=f'Over {line:g}',f'Under {line:g}'
    elif 'spread' in market:a,b=f'A {line:+g}',f'B {-line:+g}'
    else:a,b='A wins','B wins'
    text=f"{a}: {row['probability_a']:.1%} | {b}: {row['probability_b']:.1%}"
    if row['push_probability']:text+=f" | Push {row['push_probability']:.1%}"
    return text

def assessment(report):
    if report['strategy']=='MARKET-ANCHORED SCORING REFERENCE':
        return 'Market-anchored estimate; independent trained edge unavailable.'
    return 'Research only; betting accuracy requires prospective validation.'

def ranked(report):return sorted(report['priced_markets'],key=lambda r:r['ev'],reverse=True)

def best_summary(report):
    rows=ranked(report)
    if not rows:return 'No verified prices: EV unavailable.'
    best=rows[0]
    result=f"Highest calculated EV: {selection(best)} ({LABELS[best['market']][1]}), {best['ev']:+.1%}."
    if best['ev']<=0:result+=' No positive-EV priced selection.'
    else:result+=' Unvalidated estimate; not a strong-bet designation.'
    return result

def evidence(report):
    obs=report['observations'];a,b=obs['rest_minutes']['a'],obs['rest_minutes']['b']
    rest=lambda value:'unknown' if value is None else f'{value:.0f} min'
    return (f"Prior matches: A {obs['player_a_history']} | B {obs['player_b_history']} | H2H {obs['h2h_matches']}\n"
            f'Rest: A {rest(a)} | B {rest(b)}')

def render(report):
    e,d=report['event'],report['forecast']
    lines=['='*76,'🏓 CZECH LIGA PRO',f"A: {e['player_a']}",f"B: {e['player_b']}",
        f"Start (UTC): {e['start_utc']} | Captured phase: {e['status']}",'='*76,
        '📊 MATCH PROJECTION',f"{e['player_a']}: {d['p_match_a']:.1%} to win",
        f"{e['player_b']}: {1-d['p_match_a']:.1%} to win",
        f"Expected total points: {d['expected_points']:.2f} | Games: {d['expected_games']:.2f}",
        f"Expected A point margin: {d['expected_point_margin']:+.2f}",
        f"Method: {report['strategy']}",'⚠️ '+assessment(report),'','🔎 EV REVIEW',best_summary(report),
        'EV is expected return per unit staked. Odds are decimal. Win excludes pushes.',
        '','💵 PRICED MARKETS — captured sportsbook odds']
    rows=ranked(report)
    if not rows:lines.append('No fresh verified prices. EV unavailable.')
    for market in MARKETS:
        group=[r for r in rows if r['market']==market]
        if not group:continue
        lines+=['',heading(market)]
        for row in group:
            lines.append('  '+priced_line(row))
            lines.append(f"    {row['bookmaker']} | Quote (UTC): {row['quoted_utc']}")
    lines+=['','🧮 MODEL REFERENCE — unpriced projections; no EV',f"A = {e['player_a']} | B = {e['player_b']}"]
    for market in MARKETS:
        group=[r for r in report['reference_markets'] if r['market']==market]
        if group:lines+=['',heading(market)]+['  '+reference_line(r) for r in group]
    lines+=['','📚 DATA & OBSERVATIONS',evidence(report),
        'Exact match scores: '+' | '.join(f'{score}: {p:.1%}' for score,p in sorted(d['exact_scores'].items(),key=lambda item:item[1],reverse=True))]
    for g in report.get('win_cover_gaps',[]):
        rates='unavailable' if g['match_win_percentage'] is None else f"Win {g['match_win_percentage']:.1f}% | Cover {g['point_cover_percentage']:.1f}% | Gap {g['gap_percentage_points']:+.1f} pp"
        lines.append(f"Win/cover: {g['player']} {g['point_handicap']:+g} | {g['bookmaker']} | {rates} | n={g['settled_matches']} | {g['status']} (descriptive)")
    missing=[LABELS[m][1] for m in MARKETS if not any(r['market']==m for r in rows)]
    if missing:lines.append('No captured price: '+', '.join(missing))
    lines+=['','⚠️ NOTES']+list(dict.fromkeys(report.get('warnings',[])))
    lines+=['Constant independent point model; serve-specific skill unavailable.',
        f"Saved (UTC): {report['created_utc']}",'Saved output keeps its original prices and captured match state.',f"Run ID: {report['run_id']}"]
    return '\n'.join(lines)+'\n'

def chunks(lines,limit=950):
    """Keep all alternatives, splitting fields rather than silently truncating."""
    current=''
    for line in lines:
        while len(line)>limit:
            if current:yield current;current=''
            yield line[:limit];line=line[limit:]
        if len(current)+len(line)+1>limit:yield current;current=''
        current+=('\n' if current else '')+line
    if current:yield current

def discord_embeds(report):
    e,d=report['event'],report['forecast'];fields=[]
    def add(name,lines):
        for index,value in enumerate(chunks(lines),1):
            fields.append(dict(name=(name+(' (continued)' if index>1 else ''))[:256],value=value,inline=False))
    add('📊 Match projection',[f"**{e['player_a']}** — {d['p_match_a']:.1%} to win",
        f"**{e['player_b']}** — {1-d['p_match_a']:.1%} to win",
        f"Expected points **{d['expected_points']:.2f}** | Games **{d['expected_games']:.2f}**",
        f"Expected A point margin **{d['expected_point_margin']:+.2f}**"])
    add('🔎 EV review',[best_summary(report),'Decimal odds • Win excludes pushes • EV = expected return per unit'])
    rows=ranked(report)
    if not rows:add('💵 Priced markets',['No verified quotes; EV unavailable.'])
    for market in MARKETS:
        group=[r for r in rows if r['market']==market]
        if group:add(heading(market)+' • PRICED',[priced_line(r)+f" • {r['bookmaker']}" for r in group])
    add('🧮 Model reference • NO PRICES / NO EV',[f"A = {e['player_a']}\nB = {e['player_b']}"])
    for market in MARKETS:
        group=[r for r in report['reference_markets'] if r['market']==market]
        if group:add(heading(market)+' • projection',[reference_line(r) for r in group])
    add('📚 History coverage',evidence(report).splitlines())
    quote_times=sorted({r['quoted_utc'] for r in rows})
    if quote_times:add('🕒 Captured odds (UTC)',quote_times+['Upstream price age may be unknown. Saved prices are not refreshed by push.'])
    title=f"🏓 Czech Liga Pro | {e['player_a']} vs {e['player_b']}"[:256]
    start=int(timestamp(e['start_utc']).timestamp())
    description=(f"📅 Start: <t:{start}:f> • Captured phase: {e['status']}\n"
        f"**{assessment(report)}**\nMethod: {report['strategy']}\nSaved UTC: {report['created_utc']}")
    footer=report['run_id']+' • Captured report; not a live refresh'
    pages=[];page=[];base_size=len(title)+len(description)+len(footer);size=base_size
    for field in fields:
        length=len(field['name'])+len(field['value'])
        if page and (len(page)>=25 or size+length>5700):pages.append(page);page=[];size=base_size
        page.append(field);size+=length
    if page:pages.append(page)
    return [dict(title=title,description=description,color=0x3498DB,fields=page,
        footer={'text':footer+(f' • Page {i}/{len(pages)}' if len(pages)>1 else '')}) for i,page in enumerate(pages,1)]

def discord_embed(report):return discord_embeds(report)[0]

def push(report,dry_run=False):
    from discord_integration import _broadcast_embed
    total=0
    for index,embed in enumerate(discord_embeds(report)):
        # Preserve the existing first-message key; continuation pages must not
        # supersede one another when the broadcaster updates a prior report.
        key='table_tennis|'+report['event']['event_id']
        if index:key+=f'|page:{index+1}'
        total+=_broadcast_embed(embed,dry_run=dry_run,label='Czech Liga Pro research',game_key=key)
    return total
