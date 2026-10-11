"""Reproduce captured research scenarios. No live refresh, DB writes or Discord send."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def decimal(price):
    return 1 + price / 100 if price > 0 else 1 + 100 / abs(price)


def settlement(value, line, odds):
    """Return net return per unit; quarter lines split stake equally."""
    if abs(line * 2 - round(line * 2)) > 1e-8:
        lo = math.floor(line * 2) / 2
        return (settlement(value, lo, odds) + settlement(value, lo + .5, odds)) / 2
    margin = value + line
    return odds - 1 if margin > 1e-8 else -1 if margin < -1e-8 else 0


def distribution(home, away):
    rows = [(h, a, math.exp(-home-away)*home**h/math.factorial(h)*away**a/math.factorial(a))
            for h in range(30) for a in range(30)]
    mass = sum(p for _, _, p in rows)
    return [(h, a, p/mass) for h, a, p in rows]


def evaluate(rows, market):
    kind, side, line, odds = market['kind'], market['side'], market.get('line', 0), market.get('decimal')
    wins = losses = pushes = ev = 0.0
    for h, a, p in rows:
        if kind == 'ml':
            win = (h > a if side == 'home' else a > h if side == 'away' else h == a)
            ret = (odds or 2)-1 if win else -1
        elif kind == 'dc':
            win = (h >= a if side == '1X' else a >= h if side == 'X2' else h != a)
            ret = (odds or 2)-1 if win else -1
        elif kind == 'btts':
            win = (h > 0 and a > 0) == (side == 'Yes')
            ret = (odds or 2)-1 if win else -1
        elif kind == 'spread':
            ret = settlement(h-a if side == 'home' else a-h, line, odds or 2)
        else:
            value = h+a if kind == 'total' else h if kind == 'home_total' else a
            ret = settlement(value if side == 'Over' else -value,
                             -line if side == 'Over' else line, odds or 2)
        wins += p * (ret > 0)
        losses += p * (ret < 0)
        pushes += p * (ret == 0)
        ev += p*ret
    return dict(market, profit_probability=wins, loss_probability=losses,
                full_push_probability=pushes, ev_percent=100*ev if odds else None)


def quote(kind, side, odds=None, line=0, book=''):
    return dict(kind=kind, side=side, decimal=odds, line=line, book=book)


games = [
    dict(slug='hnl_gorica_v_rudes', name='HNK Gorica vs Rudes', time='12:00 PM ET', venue='Gradski stadion, Velika Gorica',
         teams=['Gorica','Rudes'], games=[8,8], gf=[5,10], ga=[12,24], confidence='Low',
         observations='Gorica won 1-0 at Istra on September 19; its preceding league match was 2-2 against Varazdin. Rudes conceded 24 in eight league games. Both league profiles list matches at Velika Gorica, so the generic home advantage may overstate venue unfamiliarity. Ante Erceg scored on his friendly return after missing the eight league rounds; a start is not confirmed. No verified complete injury list or starting XI. No opponent-adjusted xG, shot profile or player-prop inputs.',
         against='Gorica scored only five in eight games. Rudes defensive results include stronger opponents. A 6-0 cup head-to-head from 2025 is a different competition and is not included in the calculation. Neither eight-game average nor Erceg returning establishes a reliable betting edge.',
         sources=[('Official Gorica results and standings','https://hnl.hr/klubovi/gorica/'),('Official Rudes results and standings','https://hnl.hr/klubovi/rudes/'),('Coach preview','https://sport.hrt.hr/hrvatski-nogomet/carevic-morat-cemo-biti-na-maksimumu-12945300'),('Erceg friendly return','https://www.jutarnji.hr/sportske/nogomet/hnl/klubovi/gorica/gorica-bravo-kidricevo-zatvorena-utakmica-uoci-rudesa-15751814?cx_linkref=jl_ia_vezane'),('Quoted bookmaker markets','https://www.betpawa.cd/event/38315579')],
         price_note='betPawa public-page snapshot retrieved before kickoff, approximately 09:56 AM ET. Book update time unavailable; availability in your account unconfirmed.',
         markets=[quote('ml',s,o,book='betPawa') for s,o in zip(['home','draw','away'],[1.59,3.97,5.04])]
                 +[quote('btts','Yes',1.75),quote('btts','No',1.89)]
                 +[quote('dc',s,o) for s,o in [('1X',1.16),('X2',2.09),('12',1.23)]]
                 +[quote('total',s,o,l) for l,o1,o2 in [(1.5,1.20,3.75),(2.5,1.70,1.95),(3.5,2.76,1.36),(4.5,5.02,1.11),(5.5,9.22,1.01)] for s,o in [('Over',o1),('Under',o2)]]
                 +[quote(k,s,o,l) for k,sets in [('home_total',[(.5,1.11,4.93),(1.5,1.63,2.05),(2.5,2.94,1.32)]),('away_total',[(.5,1.51,2.28),(1.5,3.43,1.24),(2.5,8.25,1.02)])] for l,o1,o2 in sets for s,o in [('Over',o1),('Under',o2)]]
                 +[quote('spread',s,None,l,'Unpriced reference') for s in ['home','away'] for l in [-1.5,-1,-.5,0,.5,1,1.5]]),
    dict(slug='ligue1_lens_v_lyon', name='RC Lens vs Lyon', time='2:45 PM ET', venue='Stade Bollaert-Delelis',
         teams=['Lens','Lyon'], games=[5,5], gf=[9,10], ga=[9,2], confidence='Low',
         observations='Lyon: three wins, two draws, ten goals scored and two conceded in five league matches. Lens: one win, one draw, three losses, nine scored and nine conceded in five. Official league injury review lists Lens Abdallah Sima and Lyon Moussa Niakhate unavailable; Mohamed Ouedraogo sustained an ACL injury. Lens had returning internationals but availability must be checked against the final XI. Both clubs play in the same time zone. International-break recovery and national-team travel vary by player; they are reviewed but not assigned invented numeric adjustments.',
         against='Five matches are too few for stable defensive strength. Lyon injuries may weaken the two-goals-conceded baseline. Your stored xG fields are goal-derived proxies, not measured xG. The market expects substantially more goals than this simple goals model: that disagreement is a reason to investigate, not proof the book is wrong.',
         sources=[('Official fixture','https://ligue1.com/fr/articles/l1_article_5905-ou-et-quand-regarder-lens-lyon-j6-l1-2627'),('Official team preview','https://www.rclens.fr/fr/rc-lens-olympique-lyonnais'),('Official injury review','https://ligue1.com/fr/articles/l1_article_5908-treve-le-point-sur-les-blesses-et-les-retours-octobre-2026'),('Odds feed','https://the-odds-api.com/')],
         price_note='Pinnacle API snapshot: main markets 09:55:44 AM ET; alternative lines 09:59:01 AM ET and BTTS 09:58:34 AM ET. Captured prices, not a future live refresh.', markets=[]),
    dict(slug='women_moldova_v_georgia', name='Moldova (W) vs Georgia (W)', time='10:00 AM ET', venue='Stadionul Zimbru, Chisinau',
         teams=['Moldova W','Georgia W'], games=[4,4], gf=[2,4], ga=[1,10], confidence='Very low - PASS',
         observations='Senior women international friendly, not a qualifier; another friendly is scheduled October 12. Moldova four 2026 qualifiers: 0-1 Romania, 0-0 Cyprus, 0-0 Romania, 2-0 Cyprus. Georgia four qualifiers: 0-3 Greece, 0-1 Faroe Islands, 2-3 Faroe Islands, 2-3 Greece. The opponents differ, and these games ended in June. Moldova roster includes defenders with zero or one senior appearance, increasing rotation uncertainty. No confirmed complete Georgia injury list or final lineups. 2025 friendlies in Georgia finished 0-0 and 3-0 to Georgia; excluded from the current qualifier rates.',
         against='Four old qualifiers against different opponents cannot establish current strength for a friendly. The market favors Georgia while the raw-goals scenario favors Moldova. That reversal is a warning about comparability. Kickoff has passed: this is a captured pre-match research scenario, not an in-play recommendation.',
         sources=[('Official match announcement','https://www.fmf.md/noutate/19055/live-1700-fotbal-feminin-moldovageorgia'),('Moldova official qualifier results','https://www.fmf.md/home/nationale/femenin/echipa-nationala-1583071678/competitii-echipa-nationala-1583071678'),('UEFA qualifier ranking','https://editorial.uefa.com/resources/02a6-20d56b010275-0780b267a89d-1000/2026_weq_overall_league_rankings.pdf'),('2025 friendly results','https://fmf.md/home/nationale/femenin/echipa-nationala-1583071678/meciuri-amicale-458-1583842693?lang=ru'),('Odds comparison showing Roobet quotes','https://www.sportytrader.com/en/odds/moldova-georgia-8882568/')],
         price_note='Roobet prices displayed by Sportytrader, retrieved approximately 09:58 AM ET before kickoff. No bookmaker update timestamp; not live or executable odds confirmation.',
         markets=[quote('ml',s,o,book='Roobet via Sportytrader') for s,o in zip(['home','draw','away'],[2.92,3.05,2.32])]
                 +[quote('total',s,o,l) for l,o1,o2 in [(.5,1.04,7.4),(2.5,1.95,1.73),(3.5,3.30,1.26)] for s,o in [('Over',o1),('Under',o2)]]
                 +[quote('btts','Yes',1.73),quote('btts','No',1.96),quote('spread','home',2.10,0),quote('spread','away',1.61,0)]
                 +[quote('spread',s,None,l,'Unpriced reference') for s in ['home','away'] for l in [-1.5,-1,-.5,.5,1,1.5]])]


def main():
    # Assertions cover Asian half-win/half-loss and full-push settlement.
    assert settlement(0,.25,2)==.5 and settlement(0,-.25,2)==-.5
    assert settlement(3,-3,2)==0 and settlement(3,-2.75,2)==.5
    main_odds=json.loads((ROOT/'2026-10-09_lens_lyon_odds.json').read_text())
    extra=json.loads((ROOT/'2026-10-09_lens_lyon_extra_odds.json').read_text())
    lens=games[1]
    for event in [main_odds,extra]:
        book=next(b for b in event['bookmakers'] if b['key']=='pinnacle')
        for market in book['markets']:
            for out in market['outcomes']:
                key=market['key']
                kind={'h2h':'ml','totals':'total','alternate_totals':'total','spreads':'spread','alternate_spreads':'spread','btts':'btts'}.get(key)
                if not kind: continue
                side=out['name']
                if kind in ['ml','spread']: side='home' if side=='RC Lens' else 'away' if side=='Lyon' else 'draw'
                q=quote(kind,side,decimal(out['price']),out.get('point',0),'Pinnacle')
                if q not in lens['markets']: lens['markets'].append(q)
    (ROOT/'cards').mkdir(exist_ok=True)
    for g in games:
        home=(g['gf'][0]/g['games'][0]+g['ga'][1]/g['games'][1])/2*1.1
        away=(g['gf'][1]/g['games'][1]+g['ga'][0]/g['games'][0])/2*.9
        rows=distribution(home,away)
        assert abs(sum(p for _,_,p in rows)-1)<1e-10
        results=[evaluate(rows,q) for q in g['markets']]
        neutral=distribution(home/1.1,away/.9)
        for result,q in zip(results,g['markets']): result['neutral_venue_ev_percent']=evaluate(neutral,q)['ev_percent']
        ph=sum(p for h,a,p in rows if h>a); pd=sum(p for h,a,p in rows if h==a); pa=1-ph-pd
        top=sorted([r for r in results if r['ev_percent'] is not None],key=lambda r:r['ev_percent'],reverse=True)[:2]
        stem='2026-10-09_'+g['slug']
        def label(r):
            side = g['teams'][0] if r['side']=='home' else g['teams'][1] if r['side']=='away' else r['side']
            if r['kind']=='ml': return f'{side} win' if side!='draw' else 'Draw'
            if r['kind']=='spread': return f'{side} {r["line"]:+g} goals (Asian handicap)'
            if r['kind']=='btts': return f'Both teams score: {side}'
            if r['kind']=='dc': return f'Double chance {side}'
            prefix = 'Match' if r['kind']=='total' else g['teams'][0] if r['kind']=='home_total' else g['teams'][1]
            return f'{prefix} {side.lower()} {r["line"]:g} goals'
        pick='PASS: no strong validated bet; largest calculated EVs are research candidates only.'
        table=['| Market | Decimal odds | Profit probability | Full push | EV per stake | Neutral-venue EV |','|---|---:|---:|---:|---:|---:|']
        for r in results:
            ev='Unpriced' if r['ev_percent'] is None else f"{r['ev_percent']:+.1f}%"
            nev='Unpriced' if r['neutral_venue_ev_percent'] is None else f"{r['neutral_venue_ev_percent']:+.1f}%"
            table.append(f"| {label(r)} | {r['decimal'] or 'Not fetched'} | {r['profit_probability']:.1%} | {r['full_push_probability']:.1%} | {ev} | {nev} |")
        ml=[r for r in results if r['kind']=='ml']; vig=sum(1/r['decimal'] for r in ml)
        market_probs=', '.join(f"{r['side']} {(1/r['decimal'])/vig:.1%}" for r in ml)
        report=f"# {g['name']} — October 9, 2026\n\nRESEARCH scenario, not a validated engine recommendation. {g['time']}; {g['venue']}. Confidence: **{g['confidence']}**.\n\n{pick}\n\nCalculated home/draw/away: **{ph:.1%} / {pd:.1%} / {pa:.1%}**. Expected goals: {home:.3f}–{away:.3f}; total {home+away:.3f}. Market normalized 1X2 probabilities: {market_probs}. These normalized market probabilities remove proportional overround; they do not prove true probabilities.\n\n## Inputs and method\n\n{g['teams'][0]}: {g['gf'][0]} GF, {g['ga'][0]} GA in {g['games'][0]} matches. {g['teams'][1]}: {g['gf'][1]} GF, {g['ga'][1]} GA in {g['games'][1]} matches. Independent Poisson goals; expected home goals = mean(home GF/game, away GA/game) × 1.10; away = mean(away GF/game, home GA/game) × 0.90. These venue multipliers are assumptions from the existing force-run method, not fitted team effects. Neutral-venue sensitivity removes both multipliers. No opponent adjustment, measured xG, calibration, or quantified injury correction.\n\n## Observations and handicap review\n\n{g['observations']}\n\n## Case against / unavailable markets\n\n{g['against']} Player props, corners, cards, and half-time markets lack verified statistical inputs and are not fabricated. No betting-split or sharp-money source was verified.\n\n## Captured markets\n\n{g['price_note']} Odds are decimal (2.00 = +100). EV is expected net profit per unit staked; +10% means theoretical +0.10 per 1.00 under this scenario, not a promised return. Whole lines include refunds; quarter lines split the stake across adjacent half-lines. Profit probability includes half-wins; full-push excludes half-refunds. Unpriced spreads are fair scenario references and cannot have EV.\n\n"+'\n'.join(table)+'\n\n## Sources\n\n'+'\n'.join(f'- [{n}]({url})' for n,url in g['sources'])+'\n'
        coverage = ('In the store: Lens and Lyon have five-match 2026 domestic records, updated October 9. A past Lyon prediction exists against another opponent, but no prior prediction for this pairing was found. The standard engine run projected Lens 1.35–1.77 Lyon with home/draw/away 29.5%/23.5%/47.0%; its side and total recommendations were PASS. Its shots, corners and goal-derived xG proxies are not verified measurements for this analysis.' if g['slug'].startswith('ligue1') else
                    'Not in the store: no regular engine output for this pairing. Official league records supplied the separate research scenario; no database prediction rows were written.' if g['slug'].startswith('hnl') else
                    'Senior women records are not in the store. Stored entries named Moldova and Georgia are MEN\'S international records and must not be used for this match. No prior senior women prediction was found. This is a separate research scenario; no database rows were written.')
        report += '\n## Local coverage and standard engine\n\n'+coverage+'\n'
        (ROOT/(stem+'.md')).write_text(report,encoding='utf-8')
        (ROOT/(stem+'.json')).write_text(json.dumps(dict(inputs=g,expected_goals=[home,away],probabilities=[ph,pd,pa],markets=results),indent=2),encoding='utf-8')
        candidates='; '.join(f"{label(r)} @ {r['decimal']:.3f}: {r['ev_percent']:+.1f}% scenario EV" for r in top)
        card=dict(title=g['name'],description=f"**RESEARCH CARD - not model output.** October 9, 2026, {g['time']}. {g['venue']}.",fields=[dict(name='Market',value=g['price_note']),dict(name='Best bet',value=pick),dict(name='Calculated scenario',value=f'Home/draw/away {ph:.1%}/{pd:.1%}/{pa:.1%}. Expected goals {home:.2f}-{away:.2f}. '+candidates),dict(name='Why / observations',value=g['observations']),dict(name='Against',value=g['against']),dict(name='Check before betting',value='Final XI, actual current price, opponent-adjusted form. Captured snapshot replay does not refresh odds.'),dict(name='Confidence',value=g['confidence']),dict(name='Sharp data',value='No verified betting splits. No calibrated EV uncertainty interval.')])
        (ROOT/'cards'/(stem+'.json')).write_text(json.dumps(card,indent=2),encoding='utf-8')
        print(f"{g['name']}: {ph:.1%}/{pd:.1%}/{pa:.1%} home/draw/away | {g['confidence']}\n  {candidates}\n  {pick}\n  Report: {stem}.md")


if __name__=='__main__': main()
