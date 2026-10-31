"""AVAX backtest: football-data.org finished fixtures, chronological walk-forward.
Run: FOOTBALL_DATA_API_KEY=... python backtest.py [competition_code] [season]
Example: python backtest.py PL 2025
Only previous matches are used for each forecast. No betting guarantees.
"""
import json
import os
import sys
from collections import defaultdict
from math import exp, factorial, log
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = 'https://api.football-data.org/v4'


def fetch(path):
    token = os.getenv('FOOTBALL_DATA_API_KEY', '').strip()
    if not token:
        raise RuntimeError('FOOTBALL_DATA_API_KEY tanimli degil.')
    req = Request(API + path, headers={'X-Auth-Token': token})
    try:
        with urlopen(req, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f'API HTTP {exc.code}: erisim veya kota sorunu olabilir.') from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError('API verileri alinamadi.') from exc


def poisson(k, mean):
    return exp(-mean) * mean ** k / factorial(k)


def probabilities(home_mean, away_mean):
    p = {'home': 0., 'draw': 0., 'away': 0., 'over25': 0., 'btts': 0.}
    for i in range(21):
        for j in range(21):
            v = poisson(i, home_mean) * poisson(j, away_mean)
            p['home' if i > j else 'draw' if i == j else 'away'] += v
            if i + j >= 3:
                p['over25'] += v
            if i > 0 and j > 0:
                p['btts'] += v
    return p


def main():
    competition = sys.argv[1] if len(sys.argv) > 1 else 'PL'
    season = sys.argv[2] if len(sys.argv) > 2 else '2025'
    if not (season.isdigit() and len(season) == 4):
        raise ValueError('Sezon baslangic yili ornek: 2025')
    data = fetch(f'/competitions/{competition}/matches?season={season}&status=FINISHED')
    games = sorted(data.get('matches', []), key=lambda m: (m.get('utcDate', ''), m.get('id', 0)))
    history = defaultdict(list)
    predictions = []
    # All matches at the same kickoff timestamp are predicted before updating history.
    by_time = defaultdict(list)
    for game in games:
        by_time[game.get('utcDate', '')].append(game)
    for kickoff in sorted(by_time):
        updates = []
        for game in by_time[kickoff]:
            home = (game.get('homeTeam') or {}).get('id')
            away = (game.get('awayTeam') or {}).get('id')
            score = (game.get('score') or {}).get('fullTime') or {}
            hg, ag = score.get('home'), score.get('away')
            if not home or not away or not isinstance(hg, int) or not isinstance(ag, int):
                continue
            hhist = history[home][-10:]
            ahist = history[away][-10:]
            if len(hhist) >= 3 and len(ahist) >= 3:
                # Matches current production model: average goals scored, independent Poisson.
                hm = sum(hhist) / len(hhist)
                am = sum(ahist) / len(ahist)
                p = probabilities(hm, am)
                actual = {'home': int(hg > ag), 'draw': int(hg == ag),
                          'away': int(hg < ag), 'over25': int(hg + ag >= 3),
                          'btts': int(hg > 0 and ag > 0)}
                predictions.append((p, actual))
            updates.append((home, away, hg, ag))
        for home, away, hg, ag in updates:
            history[home].append(hg)
            history[away].append(ag)
    print(f'Lig: {competition} | Sezon: {season} | Bitmis mac: {len(games)}')
    print(f'Degerlendirilebilir mac: {len(predictions)} (takim basi en az 3 onceki mac)')
    if not predictions:
        print('Yeterli gecmis veri yok. Eksik maclar sifir sayilmadi.')
        return
    labels = [('home', 'Ev sahibi kazanir'), ('draw', 'Beraberlik'),
              ('away', 'Deplasman kazanir'), ('over25', '2.5 ust'), ('btts', 'KG var')]
    for key, label in labels:
        brier = sum((p[key] - y[key]) ** 2 for p, y in predictions) / len(predictions)
        rate = sum(y[key] for _, y in predictions) / len(predictions)
        avg = sum(p[key] for p, _ in predictions) / len(predictions)
        print(f'{label:21} Ortalama tahmin: %{avg*100:5.1f} | Gerceklesme: %{rate*100:5.1f} | Brier: {brier:.4f}')
    correct = sum(max(('home', 'draw', 'away'), key=lambda k: p[k]) ==
                  ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                  for p, y in predictions)
    print(f'Mac sonucu en yuksek olasilik isabeti: %{100*correct/len(predictions):.1f}')
    print('UYARI: Bu geriye donuk model testi; gelecekteki performansi garanti etmez.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print('HATA:', exc)
        sys.exit(1)
