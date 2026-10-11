"""Legal iid point model; explicit omitted tail, never normalized away."""
from collections import defaultdict
from functools import lru_cache
import math
from .contracts import number, score_pair, terminal, legal_terminal

class ScoringModel:
    def __init__(self, p, tolerance=1e-12):
        self.p = number(p)
        if not 0 < self.p < 1 or not 0 < tolerance < 1e-6:
            raise ValueError('Point probability must be in (0,1); tolerance in (0,1e-6)')
        self.q = 1-self.p
        self.tolerance = tolerance

    @lru_cache(None)
    def win(self, a=0, b=0):
        a, b = score_pair((a,b))
        if terminal((a,b)):
            if not legal_terminal((a,b)):
                raise ValueError('Unreachable terminal point state')
            return float(a>b)
        if min(a,b) >= 10:
            deuce = self.p**2/(self.p**2+self.q**2)
            return deuce if a==b else (self.p+self.q*deuce if a>b else self.p*deuce)
        return self.p*self.win(a+1,b)+self.q*self.win(a,b+1)

    @lru_cache(None)
    def remaining(self, a=0, b=0):
        a, b = score_pair((a,b))
        if terminal((a,b)):
            if not legal_terminal((a,b)):
                raise ValueError('Unreachable terminal point state')
            return 0.
        if min(a,b) >= 10:
            deuce = 2/(self.p**2+self.q**2)
            return deuce if a==b else 1+(self.q if a>b else self.p)*deuce
        return 1+self.p*self.remaining(a+1,b)+self.q*self.remaining(a,b+1)

    def game_scores(self, current=(0,0)):
        a,b = score_pair(current)
        self.win(a,b)  # validates state before expansion
        out = defaultdict(float)
        active = {(a,b):1.}
        # Once deuce is reached, use an analytic geometric continuation.
        deuce_entries = defaultdict(float)
        while active:
            nxt = defaultdict(float)
            for (i,j), mass in active.items():
                if terminal((i,j)):
                    out[i,j] += mass
                elif i>=10 and j>=10:
                    if i==j:
                        deuce_entries[i] += mass
                    else:
                        out[(i+1,j) if i>j else (i,j+1)] += mass*(self.p if i>j else self.q)
                        deuce_entries[max(i,j)] += mass*(self.q if i>j else self.p)
                else:
                    nxt[i+1,j] += mass*self.p
                    nxt[i,j+1] += mass*self.q
            active=nxt
        tail=0.
        cycle=2*self.p*self.q
        for tied,mass in deuce_entries.items():
            k=0
            while mass>self.tolerance:
                out[tied+k+2,tied+k] += mass*self.p**2
                out[tied+k,tied+k+2] += mass*self.q**2
                mass*=cycle
                k+=1
            tail+=mass
        return dict(out),tail

    def match(self, completed=(), current=(0,0)):
        completed=[score_pair(s) for s in completed]
        ga=gb=0
        for s in completed:
            if max(ga,gb)==3 or not legal_terminal(s):
                raise ValueError('Invalid completed game history')
            ga+=s[0]>s[1]; gb+=s[1]>s[0]
        current=score_pair(current)
        if max(ga,gb)==3 or terminal(current):
            raise ValueError('Forecast requires an unfinished match and current game')
        first,tail_first=self.game_scores(current)
        neutral,tail_neutral=self.game_scores()
        def marginals(scores):
            d={side:{'total':defaultdict(float),'margin':defaultdict(float)} for side in (0,1)}
            for (a,b),mass in scores.items():
                side=0 if a>b else 1
                d[side]['total'][a+b]+=mass
                d[side]['margin'][a-b]+=mass
            return d
        first_m=marginals(first); neutral_m=marginals(neutral)
        played_total=sum(a+b for a,b in completed)
        played_margin=sum(a-b for a,b in completed)
        totals=defaultdict(float); margins=defaultdict(float); exact=defaultdict(float)
        def convolve(left,right):
            out=defaultdict(float)
            for i,pi in left.items():
                for j,pj in right.items(): out[i+j]+=pi*pj
            return out
        # State DP merges all paths reaching a game score; totals and margins
        # need their own convolution, not a product of unrelated Poisson counts.
        states={(ga,gb):({played_total:1.},{played_margin:1.})}
        step=0
        while states:
            nxt={}
            gm=first_m if step==0 else neutral_m
            for (a,b),(td,md) in states.items():
                if max(a,b)==3:
                    exact[a,b]+=sum(td.values())
                    for k,v in td.items():totals[k]+=v
                    for k,v in md.items():margins[k]+=v
                    continue
                for side in (0,1):
                    key=(a+(side==0),b+(side==1))
                    nt,nm=nxt.setdefault(key,(defaultdict(float),defaultdict(float)))
                    for k,v in convolve(td,gm[side]['total']).items():nt[k]+=v
                    for k,v in convolve(md,gm[side]['margin']).items():nm[k]+=v
            states=nxt;step+=1
        game_totals=defaultdict(float);game_margins=defaultdict(float)
        for (a,b),mass in exact.items(): game_totals[a+b]+=mass;game_margins[a-b]+=mass
        neutral_p=self.win()
        @lru_cache(None)
        def future(a,b):
            if max(a,b)==3:return 0.
            return 1+neutral_p*future(a+1,b)+(1-neutral_p)*future(a,b+1)
        curr_p=self.win(*current)
        future_games=curr_p*future(ga+1,gb)+(1-curr_p)*future(ga,gb+1)
        expected_remaining=self.remaining(*current)+future_games*self.remaining()
        expected_total=played_total+sum(current)+expected_remaining
        # Wald's identity applies only to future points. Preserve observed margins.
        expected_margin=played_margin+current[0]-current[1]+(2*self.p-1)*expected_remaining
        @lru_cache(None)
        def match_win(a,b):
            if max(a,b)==3:return float(a==3)
            return neutral_p*match_win(a+1,b)+(1-neutral_p)*match_win(a,b+1)
        pwin=curr_p*match_win(ga+1,gb)+(1-curr_p)*match_win(ga,gb+1)
        return dict(p_match_a=pwin, p_first_game_a=self.win(*current) if not completed else None,
                    total_points=dict(totals),point_margin=dict(margins),
                    total_games=dict(game_totals),game_margin=dict(game_margins),
                    exact_scores={f'{a}-{b}':v for (a,b),v in exact.items()},
                    expected_points=expected_total,expected_point_margin=expected_margin,
                    expected_games=len(completed)+1+future_games,
                    omitted_mass=max(0.,1-sum(totals.values())),
                    first_game_scores=first if not completed else {},
                    tail_bound=tail_first+4*tail_neutral)

def settle_distribution(distribution, line, spread=False):
    win=push=loss=0.
    for value,p in distribution.items():
        difference=value+line if spread else value-line
        if difference>0:win+=p
        elif difference<0:loss+=p
        else:push+=p
    return win,loss,push
