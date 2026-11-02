import os
import time
import json
from datetime import datetime, timezone
from math import exp, factorial
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import Flask, request, render_template_string

app = Flask(__name__)
API_URL = 'https://api.football-data.org/v4'
API_CACHE = {}
CACHE_SECONDS = 300


def api_get(path):
    now = time.monotonic()
    cached = API_CACHE.get(path)

    if cached and now - cached['time'] < CACHE_SECONDS:
        return cached['data'], None

    blocked_until = API_CACHE.get('_blocked_until', 0)
    if now < blocked_until:
        if cached:
            return cached['data'], None
        return None, 'API istek sınırı doldu. Biraz bekleyin.'

    token = os.environ.get('FOOTBALL_DATA_API_KEY', '').strip()
    if not token:
        return None, 'Futbol veri anahtarı ayarlanmamış.'

    try:
        req = Request(
            API_URL + path,
            headers={'X-Auth-Token': token}
        )
        with urlopen(req, timeout=12) as response:
            data = json.load(response)

        API_CACHE[path] = {
            'data': data,
            'time': time.monotonic()
        }
        return data, None

    except HTTPError as exc:
        if exc.code == 429:
            retry = exc.headers.get('Retry-After', '60')
            try:
                wait = max(60, min(int(retry), 3600))
            except (ValueError, TypeError):
                wait = 60

            API_CACHE['_blocked_until'] = (
                time.monotonic() + wait
            )

            if cached:
                return cached['data'], None

            return None, (
                'API istek sınırına ulaşıldı. '
                'Lütfen biraz bekleyin.'
            )

        return None, f'Veri servisi HTTP {exc.code} hatası verdi.'

    except (URLError, TimeoutError, ValueError):
        if cached:
            return cached['data'], None
        return None, 'Futbol verileri şu anda alınamıyor.'


def fixtures():
    data, err = api_get('/matches?status=SCHEDULED')
    if err:
        return [], err
    matches = []
    for item in data.get('matches', [])[:100]:
        home, away = item.get('homeTeam') or {}, item.get('awayTeam') or {}
        if home.get('id') and away.get('id'):
            matches.append({'home': home.get('name', ''), 'away': away.get('name', ''),
                            'home_id': home['id'], 'away_id': away['id'],
                            'date': (item.get('utcDate') or '')[:16].replace('T', ' '),
                            'league': (item.get('competition') or {}).get('name', '')})
    return matches, None

def team_stats(team_id):
    data, err = api_get(f'/teams/{int(team_id)}/matches?status=FINISHED&limit=20')
    if err:
        return None, err
    games = []
    for match in data.get('matches', []):
        home, away = match.get('homeTeam') or {}, match.get('awayTeam') or {}
        score = (match.get('score') or {}).get('fullTime') or {}
        hg, ag = score.get('home'), score.get('away')
        if not isinstance(hg, int) or not isinstance(ag, int):
            continue
        if home.get('id') == team_id:
            games.append({'venue': 'home', 'scored': hg, 'conceded': ag,
                          'date': match.get('utcDate', '')})
        elif away.get('id') == team_id:
            games.append({'venue': 'away', 'scored': ag, 'conceded': hg,
                          'date': match.get('utcDate', '')})
    games.sort(key=lambda x: x['date'], reverse=True)
    if len(games) < 3:
        return None, 'En az 3 tamamlanmış maç gerekli.'
    def summary(items):
        if not items:
            return None
        n = len(items)
        return {'n': n, 'scored': sum(g['scored'] for g in items)/n,
                'conceded': sum(g['conceded'] for g in items)/n,
                'wins': sum(g['scored'] > g['conceded'] for g in items),
                'draws': sum(g['scored'] == g['conceded'] for g in items),
                'losses': sum(g['scored'] < g['conceded'] for g in items)}
    return {'last5': summary(games[:5]), 'last10': summary(games[:10]),
            'home': summary([g for g in games if g['venue'] == 'home']),
            'away': summary([g for g in games if g['venue'] == 'away'])}, None

def expected_goals(home_stats, away_stats):
    hs = home_stats['home'] if home_stats['home'] and home_stats['home']['n'] >= 3 else home_stats['last10']
    aw = away_stats['away'] if away_stats['away'] and away_stats['away']['n'] >= 3 else away_stats['last10']
    return round((hs['scored'] + aw['conceded']) / 2, 2), round((aw['scored'] + hs['conceded']) / 2, 2)

def poisson(k, mean):
    return exp(-mean) * mean ** k / factorial(k)

def model(h, a):
    # Independent Poisson. Period split is an assumption, not observed half-time data.
    def calc(x, y):
        r = {'home': 0., 'draw': 0., 'away': 0., 'over05': 0., 'over15': 0.,
             'over25': 0., 'over35': 0., 'btts': 0.}
        scores = []
        for i in range(41):
            pi = poisson(i, x)
            for j in range(41):
                p = pi * poisson(j, y)
                r['home' if i > j else 'draw' if i == j else 'away'] += p
                if i+j >= 1: r['over05'] += p
                if i+j >= 2: r['over15'] += p
                if i+j >= 3: r['over25'] += p
                if i+j >= 4: r['over35'] += p
                if i and j: r['btts'] += p
                scores.append((f'{i}-{j}', p))
        scores.sort(key=lambda item: item[1], reverse=True)
        return r, scores[:3]
    full, scores = calc(h, a)
    first, _ = calc(h * 0.45, a * 0.45)
    second, _ = calc(h * 0.55, a * 0.55)
    def pct(p): return round(max(0, min(1, p))*100, 1)
    def rows(r, half=False):
        output = [('Ev sahibi önde bitirir', r['home']), ('Beraberlik', r['draw']),
                  ('Deplasman önde bitirir', r['away']), ('0,5 Üst', r['over05']),
                  ('1,5 Üst', r['over15']), ('2,5 Üst', r['over25']),
                  ('2,5 Alt', 1-r['over25'])]
        if not half:
            output += [('3,5 Üst', r['over35']), ('3,5 Alt', 1-r['over35']),
                       ('KG VAR', r['btts']), ('KG YOK', 1-r['btts'])]
        return [(label, pct(value)) for label, value in output]
    return rows(full), rows(first, True), rows(second, True), [(s, pct(p)) for s, p in scores]

PAGE = '''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVAX FUTBOL ANALİZ PRO V3</title><style>body{font:16px Arial;background:#101827;color:#f1f5f9;margin:0;padding:16px}main{max-width:720px;margin:auto}h1{color:#4ade80}.card{background:#1e293b;border-radius:14px;padding:18px;margin:15px 0}button,input{box-sizing:border-box;font:inherit;padding:12px;border-radius:8px;border:0}button{background:#22c55e;color:#052e16;cursor:pointer}input{width:100%;margin:7px 0 14px}label{display:block}.match{display:block;width:100%;text-align:left;margin:7px 0;background:#334155;color:white}.muted{color:#cbd5e1;font-size:13px}.result{padding:9px;border-bottom:1px solid #475569}.error{color:#fda4af}</style></head><body><main><h1>⚽ AVAX FUTBOL ANALİZ PRO V3</h1><p class="muted">Geliştirme sürümü — kalibre edilmemiş model</p><div class="card"><h2>Güncel maçlar</h2>{% if list_error %}<p class="error">{{ list_error }}</p>{% endif %}{% if not matches %}<p>Listelenecek maç bulunamadı.</p>{% endif %}{% for m in matches %}<button class="match" type="button" data-home="{{ m.home|e }}" data-away="{{ m.away|e }}" data-home-id="{{ m.home_id }}" data-away-id="{{ m.away_id }}" onclick="choose(this)">{{ m.home }} – {{ m.away }}<br><span class="muted">{{ m.league }} · UTC {{ m.date }}</span></button>{% endfor %}</div><div class="card"><h2>Maç analizi</h2><form method="post" id="form"><label>Ev sahibi</label><input name="home" id="home" value="{{ home|e }}" required><label>Deplasman</label><input name="away" id="away" value="{{ away|e }}" required><input type="hidden" name="home_id" id="home_id" value="{{ home_id|e }}"><input type="hidden" name="away_id" id="away_id" value="{{ away_id|e }}"><label>Ev sahibi beklenen gol</label><input type="number" step="0.01" min="0" max="10" name="hg" id="hg" value="{{ hg|e }}"><label>Deplasman beklenen gol</label><input type="number" step="0.01" min="0" max="10" name="ag" id="ag" value="{{ ag|e }}"><button type="submit">MAÇI ANALİZ ET</button></form><p class="muted">Maça dokununca takım adları ve gol ortalamaları otomatik hesaplanır. Gerekirse gol değerlerini elle girebilirsin.</p>{% if error %}<p class="error">{{ error }}</p>{% endif %}</div>{% if stats %}<div class="card"><h2>Takım formu</h2>{% for name, data in stats %}<h3>{{ name }}</h3>{% for label, item in [('Son 5',data.last5),('Son 10',data.last10),('İç saha',data.home),('Deplasman',data.away)] %}{% if item %}<div class="result">{{ label }} ({{ item.n }} maç): {{ item.wins }}G {{ item.draws }}B {{ item.losses }}M · Atılan {{ '%.2f'|format(item.scored) }} · Yenilen {{ '%.2f'|format(item.conceded) }}</div>{% endif %}{% endfor %}{% endfor %}</div>{% endif %}{% if results %}<div class="card"><h2>Maç sonucu ve gol seçenekleri</h2>{% for label, value in results %}<div class="result">{{ label }}: %{{ value }}</div>{% endfor %}</div><div class="card"><h2>İlk yarı tahminleri</h2>{% for label, value in first %}<div class="result">{{ label }}: %{{ value }}</div>{% endfor %}</div><div class="card"><h2>İkinci yarı tahminleri</h2>{% for label, value in second %}<div class="result">{{ label }}: %{{ value }}</div>{% endfor %}</div><div class="card"><h2>En olası 3 maç skoru</h2>{% for score, value in scores %}<div class="result">{{ score }} — %{{ value }}</div>{% endfor %}</div><p class="muted">Bağımsız Poisson tahminleri kalibre edilmemiştir. İlk yarı %45, ikinci yarı %55 gol payı varsayılmıştır; gerçek devre verisine dayanmaz. Yüzdeler güven veya kazanma garantisi değildir.</p>{% endif %}</main><script>function choose(b){document.getElementById('home').value=b.dataset.home;document.getElementById('away').value=b.dataset.away;document.getElementById('home_id').value=b.dataset.homeId;document.getElementById('away_id').value=b.dataset.awayId;document.getElementById('hg').value='';document.getElementById('ag').value='';document.getElementById('form').submit()}</script></body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    matches, list_error = fixtures()
    values = {k: '' for k in ('home','away','home_id','away_id','hg','ag')}
    results = first = second = scores = stats = error = None
    if request.method == 'POST':
        values = {k: request.form.get(k, '').strip() for k in values}
        try:
            home_id, away_id = int(values['home_id']), int(values['away_id'])
        except (ValueError, TypeError):
            home_id = away_id = None
        if home_id and away_id:
            hs, eh = team_stats(home_id)
            aw, ea = team_stats(away_id)
            if hs and aw:
                stats = [(values['home'], hs), (values['away'], aw)]
                if not values['hg'] or not values['ag']:
                    h, a = expected_goals(hs, aw)
                    values['hg'], values['ag'] = str(h), str(a)
            elif not values['hg'] or not values['ag']:
                error = 'Otomatik veri eksik: ' + '; '.join(dict.fromkeys(x for x in (eh, ea) if x)) + ' Gol değerlerini elle girebilirsin.'
        if values['hg'] and values['ag']:
            try:
                h, a = float(values['hg']), float(values['ag'])
                if not (0 <= h <= 10 and 0 <= a <= 10):
                    raise ValueError()
                results, first, second, scores = model(h, a)
            except ValueError:
                error = 'Gol değerleri 0 ile 10 arasında olmalıdır.'
    return render_template_string(PAGE, matches=matches, list_error=list_error,
                                  results=results, first=first, second=second,
                                  scores=scores, stats=stats, error=error, **values)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
