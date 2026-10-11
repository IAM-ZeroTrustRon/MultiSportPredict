"""Auxiliary count diagnostic, never a legal table-tennis score generator."""
import math
from .contracts import number

def poisson_distribution(rate,tolerance=1e-10,max_count=1000):
    rate=number(rate)
    if rate<0 or not 0<tolerance<1 or max_count<0 or int(max_count)!=max_count:
        raise ValueError('Invalid Poisson rate, tolerance or count limit')
    probabilities=[]
    for k in range(int(max_count)+1):
        mass=(1. if k==0 else 0.) if rate==0 else math.exp(-rate+k*math.log(rate)-math.lgamma(k+1))
        probabilities.append(mass)
        if k>=rate and 1-math.fsum(probabilities)<=tolerance:break
    return dict(probabilities=probabilities,tail_mass=max(0.,1-math.fsum(probabilities)))

def losing_points_diagnostic(events):
    points=[min(a,b) for e in events for a,b in e['game_scores']]
    if len(points)<2:return dict(sample_size=len(points),status='Need at least two observed games')
    mean=sum(points)/len(points);variance=sum((x-mean)**2 for x in points)/(len(points)-1)
    return dict(sample_size=len(points),mean=mean,variance=variance,
                dispersion_ratio=variance/mean if mean else None,
                use='Diagnostic only: stopped game scores are not independent Poisson counts')
