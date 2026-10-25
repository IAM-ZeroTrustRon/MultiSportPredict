"""Team 5-on-5 NHL benchmark: regulation Poisson rates plus fitted OT/SO winner."""
import datetime as dt
import math
import numpy as np
from scipy.stats import poisson, skellam
from sklearn.linear_model import PoissonRegressor, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_poisson_deviance, log_loss

from features.nhl_features import NHL_FEATURES, FEATURE_VERSION


def vector(features):
    if any(k not in features or isinstance(features[k],bool) or not math.isfinite(float(features[k])) for k in NHL_FEATURES):
        raise ValueError("NHL feature contract has missing/nonfinite values; no imputation permitted")
    return [float(features[k]) for k in NHL_FEATURES]


def distribution(home,away,ot_home,epsilon=1e-10):
    if any(not math.isfinite(x) or not 0<x<20 for x in (home,away)):
        raise ValueError("NHL scoring intensity outside defensible numeric range")
    if ot_home is None:return None
    if not 0<ot_home<1:raise ValueError("Invalid fitted overtime probability")
    limit=int(max(poisson.ppf(1-epsilon,home),poisson.ppf(1-epsilon,away)))
    joint={};regulation={"home":0.,"draw":0.,"away":0.}
    hp=poisson.pmf(np.arange(limit+1),home);ap=poisson.pmf(np.arange(limit+1),away)
    for h in range(limit+1):
        for a in range(limit+1):
            mass=float(hp[h]*ap[a])
            regulation["home" if h>a else "away" if a>h else "draw"]+=mass
            if h==a:
                joint[h+1,a]=joint.get((h+1,a),0)+mass*ot_home
                joint[h,a+1]=joint.get((h,a+1),0)+mass*(1-ot_home)
            else:joint[h,a]=joint.get((h,a),0)+mass
    return dict(scores=joint,regulation=regulation,omitted_tail=max(0.,1-sum(joint.values())))


def market_probabilities(d,kind,line):
    if d is None:return None
    if kind not in {"moneyline","spread","total"}:raise ValueError("Unsupported NHL market")
    if kind!="moneyline" and (not math.isfinite(float(line)) or abs(line*2-round(line*2))>1e-8):
        raise ValueError("NHL supports integer/half lines only")
    win=loss=push=0.
    for (h,a),p in d["scores"].items():
        value=h-a if kind=="moneyline" else h-a+line if kind=="spread" else h+a-line
        if value>0:win+=p
        elif value<0:loss+=p
        else:push+=p
    return win,loss,push


class NHLModel:
    def fit(self,rows,data_hash,cutoff):
        from nhl_sources import stamp
        if any((stamp(r['start_time'])>=stamp(cutoff)) if r.get('start_time') else r['date']>cutoff[:10] for r in rows):
            raise ValueError('Training rows extend beyond the declared model cutoff')
        if len(rows)<500:raise ValueError("Need 500 eligible historical NHL examples")
        rows=sorted(rows,key=lambda r:r["date"])
        boundary=rows[int(len(rows)*.8)]["date"]
        train=[r for r in rows if r["date"]<boundary];test=[r for r in rows if r["date"]>=boundary]
        if len(train)<300 or len(test)<100:raise ValueError("Insufficient chronological NHL validation")
        def fit_on(items):
            x=np.array([vector(r) for r in items]);models=[]
            for side in ("home","away"):
                y=np.array([r["regulation_"+side] for r in items],dtype=float)
                model=make_pipeline(StandardScaler(),PoissonRegressor(alpha=.3,max_iter=1000))
                model.fit(x,y);models.append(model)
            tied=[r for r in items if r["regulation_home"]==r["regulation_away"]]
            ot=None
            if len(tied)>=50 and len({r["home_won"] for r in tied})==2:
                ot=make_pipeline(StandardScaler(),LogisticRegression(C=.2,max_iter=1000))
                ot.fit([vector(r) for r in tied],[r["home_won"] for r in tied])
            return models,ot
        models,ot=fit_on(train);x=np.array([vector(r) for r in test])
        means=[m.predict(x) for m in models]
        deviances=[];baseline=[];dispersion=[]
        for side,predicted in zip(("home","away"),means):
            actual=np.array([r["regulation_"+side] for r in test]);base=np.mean([r["regulation_"+side] for r in train])
            deviances.append(mean_poisson_deviance(actual,predicted))
            baseline.append(mean_poisson_deviance(actual,np.full(len(actual),base)))
            dispersion.append(float(np.mean((actual-predicted)**2/predicted)))
        probabilities=[]
        if ot is not None:
            ot_ps=ot.predict_proba(x)[:,1]
            for h,a,p in zip(means[0],means[1],ot_ps):
                probabilities.append(float(1-skellam.cdf(0,h,a)+skellam.pmf(0,h,a)*p))
        actual=[r["home_won"] for r in test];base_home=np.mean([r["home_won"] for r in train])
        self.validation=dict(method="Chronological 80/20 whole-date holdout; training-fold scalers only",
                             games=len(test),training_games=len(train),boundary=boundary,
                             goal_deviance=float(np.mean(deviances)),baseline_goal_deviance=float(np.mean(baseline)),
                             goal_dispersion=dispersion,
                             winner_brier=float(np.mean((np.array(probabilities)-actual)**2)) if probabilities else None,
                             baseline_winner_brier=float(np.mean((base_home-np.array(actual))**2)),
                             winner_log_loss=float(log_loss(actual,probabilities,labels=[0,1])) if probabilities else None,
                             historical_odds_benchmark=None,
                             historical_odds_benchmark_reason="No archived historical NHL quotes are stored; the no-vig market benchmark cannot be reconstructed without inventing prices",
                             dispersion_limit=1.5,
                             limitations="Historical reconstruction with current MoneyPuck xG revision; not a forward-tested edge")
        self.models,self.ot=fit_on(rows)
        self.feature_schema=list(NHL_FEATURES);self.feature_version=FEATURE_VERSION
        self.data_hash=data_hash;self.created_utc=dt.datetime.now(dt.timezone.utc).isoformat()
        self.trained_before=cutoff;self.version="nhl-team-5v5-st-poisson-ot-v2"
        return self

    def predict(self,features,playoff=False):
        if self.feature_schema!=NHL_FEATURES or self.feature_version!=FEATURE_VERSION:
            raise ValueError("NHL model/feature schema mismatch; run train_nhl.py")
        x=[vector(features)];h,a=[float(m.predict(x)[0]) for m in self.models]
        ot=None if self.ot is None or playoff else float(self.ot.predict_proba(x)[0,1])
        return dict(regulation_home=h,regulation_away=a,ot_home_probability=ot,
                    distribution=distribution(h,a,ot))
