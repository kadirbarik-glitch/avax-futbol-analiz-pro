"""AVAX V3.4 - five-league historical, pre-match-only backtest.

Run with FOOTBALL_DATA_API_KEY configured:
    python backtest_v4.py 2025
    python backtest_v4.py 2025 PL

Season is the football-data.org starting year. Each competition is evaluated
separately, using only earlier matches from that competition and season.
"""
import os
import sys
import json
import time
from math import exp, factorial
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'https://api.football-data.org/v4'
LEAGUES = {'PL': 'Premier League', 'PD': 'La Liga', 'SA': 'Serie A',
           'BL1': 'Bundesliga', 'FL1': 'Ligue 1'}
MARKETS = [('home', 'MS1'), ('draw', 'Beraberlik'), ('away', 'MS2'),
           ('over25', '2.5 Ust'), ('btts', 'KG VAR')]


def fetch(path):
    token = os.environ.get('FOOTBALL_DATA_API_KEY', '').strip()
    if not token:
        raise RuntimeError('FOOTBALL_DATA_API_KEY eksik')
    req = Request(BASE + path, headers={'X-Auth-Token': token})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise RuntimeError(f'API HTTP {exc.code} ({path})') from exc
            retry = exc.headers.get('Retry-After', '65')
            try:
                delay = max(65, min(int(retry), 180))
            except (ValueError, TypeError):
                delay = 65
            print(f'API siniri: {delay} saniye bekleniyor...', flush=True)
            time.sleep(delay)
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f'Baglanti hatasi: {exc}') from exc


def poisson(k, mean):
    return exp(-mean) * mean ** k / factorial(k)


def predict(h, a):
    out = {'home': 0., 'draw': 0., 'away': 0., 'over25': 0., 'btts': 0.}
    hp = [poisson(i, h) for i in range(26)]
    ap = [poisson(j, a) for j in range(26)]
    for i in range(26):
        for j in range(26):
            p = hp[i] * ap[j]
            out['home' if i > j else 'draw' if i == j else 'away'] += p
            if i + j >= 3:
                out['over25'] += p
            if i and j:
                out['btts'] += p
    return out


def summary(games):
    if not games:
        return None
    return {'n': len(games), 'scored': sum(g[1] for g in games) / len(games),
            'conceded': sum(g[2] for g in games) / len(games)}


def evaluate(matches):
    history = {}
    rows = []
    matches.sort(key=lambda m: (m['utcDate'], m['id']))
    pos = 0
    while pos < len(matches):
        end = pos + 1
        while end < len(matches) and matches[end]['utcDate'] == matches[pos]['utcDate']:
            end += 1
        batch = matches[pos:end]
        for m in batch:
            hid, aid = m['homeTeam']['id'], m['awayTeam']['id']
            home_hist, away_hist = history.get(hid, []), history.get(aid, [])
            if len(home_hist) < 3 or len(away_hist) < 3:
                continue
            hs = summary([x for x in home_hist[-20:] if x[0] == 'home'])
            aw = summary([x for x in away_hist[-20:] if x[0] == 'away'])
            hs = hs if hs and hs['n'] >= 3 else summary(home_hist[-10:])
            aw = aw if aw and aw['n'] >= 3 else summary(away_hist[-10:])
            h = min(10., max(0., (hs['scored'] + aw['conceded']) / 2))
            a = min(10., max(0., (aw['scored'] + hs['conceded']) / 2))
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


def valid_matches(data):
    return [m for m in data.get('matches', [])
            if m.get('utcDate') and m.get('id') is not None
            and (m.get('homeTeam') or {}).get('id') is not None
            and (m.get('awayTeam') or {}).get('id') is not None
            and isinstance(((m.get('score') or {}).get('fullTime') or {}).get('home'), int)
            and isinstance(((m.get('score') or {}).get('fullTime') or {}).get('away'), int)]


def report(code, season, matches, rows):
    print(f'\n{LEAGUES[code]} ({code}) | Sezon: {season} | Tamamlanan: {len(matches)} | Test edilen: {len(rows)}')
    if not rows:
        print('Yeterli mac yok.')
        return
    n = len(rows)
    for key, name in MARKETS:
        avg = sum(p[key] for p, y in rows) / n
        actual = sum(y[key] for p, y in rows) / n
        brier = sum((p[key] - y[key]) ** 2 for p, y in rows) / n
        baseline = sum((actual - y[key]) ** 2 for p, y in rows) / n
        print(f'{name}: Tahmin %{avg*100:.1f} | Gercek %{actual*100:.1f} | '
              f'Brier {brier:.4f} | Sabit oran baz cizgisi {baseline:.4f}*')
    correct = sum(max(('home', 'draw', 'away'), key=lambda k: p[k]) ==
                  ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                  for p, y in rows)
    print(f'Mac sonucu en yuksek olasilik isabeti: %{100 * correct / n:.1f}')


def main():
    season = sys.argv[1] if len(sys.argv) > 1 else '2025'
    selected = sys.argv[2].upper() if len(sys.argv) > 2 else None
    if not (season.isdigit() and len(season) == 4):
        raise SystemExit('Kullanim: python backtest_v4.py 2025 [PL|PD|SA|BL1|FL1]')
    if selected and selected not in LEAGUES:
        raise SystemExit('Gecersiz lig kodu: ' + selected)
    codes = [selected] if selected else list(LEAGUES)
    all_rows = []
    failures = []
    for idx, code in enumerate(codes):
        if idx:
            time.sleep(7)
        try:
            data = fetch(f'/competitions/{code}/matches?season={season}&status=FINISHED')
            matches = valid_matches(data)
            rows = evaluate(matches)
            report(code, season, matches, rows)
            all_rows.extend(rows)
        except RuntimeError as exc:
            print(f'\n{code}: HATA - {exc}', flush=True)
            failures.append(code)
    if all_rows:
        print(f'\nTOPLAM TEST EDILEN: {len(all_rows)}')
        correct = sum(max(('home', 'draw', 'away'), key=lambda k: p[k]) ==
                      ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                      for p, y in all_rows)
        print(f'Agirlikli mac sonucu isabeti: %{100 * correct / len(all_rows):.1f}')
    print('* Baz cizgisi tum test sonuclari kullanilarak hesaplanmistir; '
          'ileri donuk, veri sizintisiz bir karsilastirma degildir.')
    print('Geriye donuk testtir; gelecekte kazanc garantisi vermez.')
    if failures or not all_rows:
        raise SystemExit('Eksik veya basarisiz lig testleri: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
