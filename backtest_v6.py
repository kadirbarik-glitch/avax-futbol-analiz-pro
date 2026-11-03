"""AVAX V3.5 opponent-strength backtest. Run: python backtest_v6.py [PL|PD|SA|BL1|FL1].
2024 selects strength blending; 2025 is held out. API key via environment.
"""
import os, sys, json, time
from collections import defaultdict
from math import exp, factorial
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

LEAGUES = {'PL':'Premier League','PD':'La Liga','SA':'Serie A','BL1':'Bundesliga','FL1':'Ligue 1'}
MARKETS = ('home','draw','away','over25','btts')
BASE = 'https://api.football-data.org/v4'

def fetch(code, season):
    key = os.environ.get('FOOTBALL_DATA_API_KEY', '').strip()
    if not key: raise RuntimeError('FOOTBALL_DATA_API_KEY missing')
    url = f'{BASE}/competitions/{code}/matches?season={season}&status=FINISHED'
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'X-Auth-Token':key}), timeout=30) as response:
                return json.load(response).get('matches', [])
        except HTTPError as e:
            if e.code != 429 or attempt == 3: raise RuntimeError(f'HTTP {e.code}') from e
            try: wait = int(e.headers.get('Retry-After','60'))
            except ValueError: wait = 60
            time.sleep(max(60,min(wait,180)))
        except (URLError, TimeoutError) as e:
            raise RuntimeError(f'Network error: {e}') from e

def valid(matches):
    result=[]
    for m in matches:
        home,away=m.get('homeTeam') or {},m.get('awayTeam') or {}
        score=(m.get('score') or {}).get('fullTime') or {}
        if (m.get('utcDate') and m.get('id') is not None and home.get('id') is not None
            and away.get('id') is not None and type(score.get('home')) is int
            and type(score.get('away')) is int): result.append(m)
    return sorted(result,key=lambda x:(x['utcDate'],x['id']))

def poisson(k,mean): return exp(-mean)*mean**k/factorial(k)

def probabilities(h,a):
    hp=[poisson(i,h) for i in range(26)]
    ap=[poisson(i,a) for i in range(26)]
    out=dict.fromkeys(MARKETS,0.0)
    for i,ph in enumerate(hp):
        for j,pa in enumerate(ap):
            p=ph*pa
            out['home' if i>j else 'draw' if i==j else 'away']+=p
            if i+j>=3: out['over25']+=p
            if i and j: out['btts']+=p
    return out

def mean(rows,index): return sum(x[index] for x in rows)/len(rows)

def expected(history,hid,aid,blend):
    hh=history[hid][-20:]; aa=history[aid][-20:]
    if len(hh)<3 or len(aa)<3: return None
    home=[r for r in hh if r[0]=='home']; away=[r for r in aa if r[0]=='away']
    home=home if len(home)>=3 else hh[-10:]
    away=away if len(away)>=3 else aa[-10:]
    simple_h=(mean(home,1)+mean(away,2))/2
    simple_a=(mean(away,1)+mean(home,2))/2
    # Opponent-adjusted goals use ONLY opponent strength available before each prior match.
    def adjusted(rows,field):
        return sum(r[field]/max(.4,min(2.5,r[3 if field==1 else 4])) for r in rows)/len(rows)
    strong_h=(adjusted(home,1)+adjusted(away,2))/2
    strong_a=(adjusted(away,1)+adjusted(home,2))/2
    return (min(8,max(.05,(1-blend)*simple_h+blend*strong_h)),
            min(8,max(.05,(1-blend)*simple_a+blend*strong_a)))

def evaluate(matches,blend):
    history=defaultdict(list); rows=[]
    # Strength is computed from prior games; batch equal kickoffs to avoid leakage.
    pos=0
    while pos<len(matches):
        end=pos+1
        while end<len(matches) and matches[end]['utcDate']==matches[pos]['utcDate']: end+=1
        batch=matches[pos:end]
        updates=[]
        for m in batch:
            hid=m['homeTeam']['id']; aid=m['awayTeam']['id']
            hg=m['score']['fullTime']['home']; ag=m['score']['fullTime']['away']
            ex=expected(history,hid,aid,blend)
            if ex:
                p=probabilities(*ex)
                y={'home':int(hg>ag),'draw':int(hg==ag),'away':int(hg<ag),
                   'over25':int(hg+ag>=3),'btts':int(hg>0 and ag>0)}
                rows.append((p,y))
            # Estimate opponent defensive/attacking strength from matches before kickoff.
            def strength(team,field):
                recent=history[team][-10:]
                return max(.4,min(2.5,mean(recent,field)/1.4)) if len(recent)>=3 else 1.0
            updates.append((hid,aid,hg,ag,strength(aid,2),strength(aid,1),
                            strength(hid,2),strength(hid,1)))
        for hid,aid,hg,ag,ad,aa,hd,ha in updates:
            history[hid].append(('home',hg,ag,ad,aa))
            history[aid].append(('away',ag,hg,hd,ha))
        pos=end
    return rows

def score(rows):
    return sum(sum((p[k]-y[k])**2 for k in MARKETS) for p,y in rows)/(len(rows)*len(MARKETS))

def report(code):
    train=valid(fetch(code,'2024'))
    time.sleep(7)
    test=valid(fetch(code,'2025'))
    if len(train)<100 or len(test)<100: raise RuntimeError('Insufficient matches')
    options=(0.0,0.25,0.5,0.75,1.0)
    training={w:evaluate(train,w) for w in options}
    chosen=min(options,key=lambda w:score(training[w]))
    raw=evaluate(test,0.0); new=evaluate(test,chosen)
    if len(raw)!=len(new): raise RuntimeError('Mismatched evaluation counts')
    print(f'\n{LEAGUES[code]} | train 2024={len(training[chosen])} | test 2025={len(new)} | selected weight={chosen:.2f}')
    print(f'Average Brier: baseline={score(raw):.4f} | strength={score(new):.4f}')
    for k in MARKETS:
        b=sum((p[k]-y[k])**2 for p,y in raw)/len(raw)
        n=sum((p[k]-y[k])**2 for p,y in new)/len(new)
        print(f'{k}: baseline={b:.4f} | strength={n:.4f}')
    for label,rows in [('baseline',raw),('strength',new)]:
        accuracy=sum(max(('home','draw','away'),key=lambda k:p[k])==
                     ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                     for p,y in rows)/len(rows)
        print(f'{label} match-result accuracy={accuracy:.1%}')

def main():
    codes=[sys.argv[1].upper()] if len(sys.argv)>1 else list(LEAGUES)
    if any(c not in LEAGUES for c in codes): raise SystemExit('Unknown league code')
    failed=[]
    for i,code in enumerate(codes):
        if i: time.sleep(7)
        try: report(code)
        except RuntimeError as e:
            print(f'{code}: ERROR {e}',flush=True); failed.append(code)
    print('\n2025 is held out for evaluation. No profit guarantee.')
    if failed: raise SystemExit('Incomplete: '+', '.join(failed))

if __name__=='__main__': main()
