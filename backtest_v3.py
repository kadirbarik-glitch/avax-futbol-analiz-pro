"""AVAX V3.3: historical, pre-match-only probability backtest.
Run: FOOTBALL_DATA_API_KEY=... python backtest_v3.py PL 2025
Season format is football-data.org season start year.
"""
import os
import sys
import json
import time
from math import exp, factorial
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = 'https://api.football-data.org/v4'

def fetch(path):
    key = os.environ.get('FOOTBALL_DATA_API_KEY', '').strip()
    if not key:
        raise RuntimeError('FOOTBALL_DATA_API_KEY eksik')
    req = Request(BASE + path, headers={'X-Auth-Token': key})
    try:
        with urlopen(req, timeout=25) as r:
            return json.load(r)
    except HTTPError as e:
        raise RuntimeError(f'API HTTP {e.code}; istek sinirini kontrol edin') from e

def poisson(k, mean):
    return exp(-mean) * mean**k / factorial(k)

def predict(h, a):
    out = {'home': 0., 'draw': 0., 'away': 0., 'over25': 0., 'btts': 0.}
    for i in range(26):
        for j in range(26):
            p = poisson(i, h) * poisson(j, a)
            out['home' if i > j else 'draw' if i == j else 'away'] += p
            if i + j >= 3:
                out['over25'] += p
            if i and j:
                out['btts'] += p
    return out

def summary(games):
    if not games:
        return None
    return {'n': len(games), 'scored': sum(x[1] for x in games)/len(games),
            'conceded': sum(x[2] for x in games)/len(games)}

def evaluate(matches):
    history = {}
    rows = []
    # Same kickoff group is predicted before adding any results from that group.
    matches.sort(key=lambda m: (m['utcDate'], m['id']))
    pos = 0
    while pos < len(matches):
        end = pos + 1
        while end < len(matches) and matches[end]['utcDate'] == matches[pos]['utcDate']:
            end += 1
        batch = matches[pos:end]
        for m in batch:
            hid, aid = m['homeTeam']['id'], m['awayTeam']['id']
            home_hist = history.get(hid, [])
            away_hist = history.get(aid, [])
            if len(home_hist) < 3 or len(away_hist) < 3:
                continue
            hs = summary([x for x in home_hist[-20:] if x[0] == 'home'])
            aw = summary([x for x in away_hist[-20:] if x[0] == 'away'])
            hs = hs if hs and hs['n'] >= 3 else summary(home_hist[-10:])
            aw = aw if aw and aw['n'] >= 3 else summary(away_hist[-10:])
            h = min(10., max(0., (hs['scored'] + aw['conceded'])/2))
            a = min(10., max(0., (aw['scored'] + hs['conceded'])/2))
            p = predict(h, a)
            hg, ag = m['score']['fullTime']['home'], m['score']['fullTime']['away']
            actual = {'home': int(hg > ag), 'draw': int(hg == ag),
                      'away': int(hg < ag), 'over25': int(hg + ag >= 3),
                      'btts': int(hg > 0 and ag > 0)}
            rows.append((p, actual))
        for m in batch:
            hid, aid = m['homeTeam']['id'], m['awayTeam']['id']
            hg, ag = m['score']['fullTime']['home'], m['score']['fullTime']['away']
            history.setdefault(hid, []).append(('home', hg, ag))
            history.setdefault(aid, []).append(('away', ag, hg))
        pos = end
    return rows

def main():
    league = sys.argv[1] if len(sys.argv) > 1 else 'PL'
    season = sys.argv[2] if len(sys.argv) > 2 else '2025'
    data = fetch(f'/competitions/{league}/matches?season={season}&status=FINISHED')
    matches = [m for m in data.get('matches', [])
               if m.get('utcDate') and m.get('id') is not None
               and (m.get('homeTeam') or {}).get('id') is not None
               and (m.get('awayTeam') or {}).get('id') is not None
               and isinstance(((m.get('score') or {}).get('fullTime') or {}).get('home'), int)
               and isinstance(((m.get('score') or {}).get('fullTime') or {}).get('away'), int)]
    rows = evaluate(matches)
    print(f'Lig: {league} | Sezon: {season} | Tamamlanan: {len(matches)} | Test edilen: {len(rows)}')
    if not rows:
        print('Test icin yeterli gecmis mac yok.')
        return
    for key, name in [('home', 'MS1'), ('draw', 'Beraberlik'), ('away', 'MS2'),
                      ('over25', '2.5 Ust'), ('btts', 'KG VAR')]:
        avg = sum(p[key] for p, y in rows)/len(rows)
        actual = sum(y[key] for p, y in rows)/len(rows)
        brier = sum((p[key] - y[key])**2 for p, y in rows)/len(rows)
        print(f'{name}: Tahmin ort. %{avg*100:.1f} | Gercek %{actual*100:.1f} | Brier {brier:.4f}')
    correct = sum(max(('home', 'draw', 'away'), key=lambda k: p[k]) ==
                  ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                  for p, y in rows)
    print(f'Mac sonucu en yuksek olasilik isabeti: %{100*correct/len(rows):.1f}')
    print('Geriye donuk testtir; gelecekte kazanc garantisi vermez.')

if __name__ == '__main__':
    main()
