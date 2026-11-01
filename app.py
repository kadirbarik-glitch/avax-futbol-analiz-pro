import os
import json
from datetime import datetime, timezone
from math import exp, factorial
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import Flask, request, render_template_string

app = Flask(__name__)
API_URL = 'https://api.football-data.org/v4'

def api_get(path):
    token = os.environ.get('FOOTBALL_DATA_API_KEY', '').strip()
    if not token:
        return None, 'Futbol veri anahtarı ayarlanmamış.'
    try:
        req = Request(API_URL + path, headers={'X-Auth-Token': token})
        with urlopen(req, timeout=12) as response:
            return json.load(response), None
    except HTTPError as exc:
        return None, f'Veri servisi HTTP {exc.code} hatası verdi.'
    except (URLError, TimeoutError, ValueError):
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
            games.append({'venue': 'home', 'scored': hg, 'conceded': ag})
        elif away.get('id') == team_id:
            games.append({'venue': 'away', 'scored': ag, 'conceded': hg})
    if len(games) < 3:
        return None, 'En az 3 tamamlanmış maç gerekli.'
    def average(items, key):
        return sum(g[key] for g in items) / len(items)
    def summary(items):
        return {'n': len(items), 'scored': average(items, 'scored'),
                'conceded': average(items, 'conceded')} if items else None
    return {'last5': summary(games[:5]), 'last10': summary(games[:10]),
            'home': summary([g for g in games if g['venue'] == 'home']),
            'away': summary([g for g in games if g['venue'] == 'away'])}, None

def expected_goals(home_stats, away_stats):
    # Basit sezgisel yaklaşım; gerçek xG veya kalibre edilmiş model değildir.
    hs = home_stats['home'] if home_stats['home'] and home_stats['home']['n'] >= 3 else home_stats['last10']
    aw = away_stats['away'] if away_stats['away'] and away_stats['away']['n'] >= 3 else away_stats['last10']
    return round((hs['scored'] + aw['conceded']) / 2, 2), round((aw['scored'] + hs['conceded']) / 2, 2)

def poisson(k, mean):
    return exp(-mean) * mean ** k / factorial(k)

def probabilities(h, a):
    # 0..40 aralığı, beklenen gol <=10 iken ihmal edilebilir kuyruk bırakır.
    result = {'home': 0., 'draw': 0., 'away': 0., 'over15': 0., 'over25': 0., 'over35': 0., 'btts': 0.}
    scores = []
    for i in range(41):
        ph = poisson(i, h)
        for j in range(41):
            p = ph * poisson(j, a)
            result['home' if i > j else 'draw' if i == j else 'away'] += p
            if i + j >= 2: result['over15'] += p
            if i + j >= 3: result['over25'] += p
            if i + j >= 4: result['over35'] += p
            if i and j: result['btts'] += p
            scores.append((f'{i}-{j}', p))
    scores.sort(key=lambda x: x[1], reverse=True)
    labels = [('Ev sahibi kazanır', result['home']), ('Beraberlik', result['draw']),
              ('Deplasman kazanır', result['away']), ('1,5 Üst', result['over15']),
              ('2,5 Üst', result['over25']), ('2,5 Alt', 1-result['over25']),
              ('3,5 Üst', result['over35']), ('3,5 Alt', 1-result['over35']),
              ('Karşılıklı gol VAR', result['btts']), ('Karşılıklı gol YOK', 1-result['btts'])]
    return [(label, round(p*100, 1)) for label, p in labels], [(s, round(p*100, 1)) for s, p in scores[:3]]

PAGE = '''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVAX FUTBOL ANALİZ PRO V3</title><style>body{font:16px Arial;background:#101827;color:#f1f5f9;margin:0;padding:16px}main{max-width:720px;margin:auto}h1{color:#4ade80}.card{background:#1e293b;border-radius:14px;padding:18px;margin:15px 0}button,input{box-sizing:border-box;font:inherit;padding:12px;border-radius:8px;border:0}button{background:#22c55e;color:#052e16;cursor:pointer}input{width:100%;margin:7px 0 14px}label{display:block}.match{display:block;width:100%;text-align:left;margin:7px 0;background:#334155;color:white}.muted{color:#cbd5e1;font-size:13px}.result{padding:9px;border-bottom:1px solid #475569}.error{color:#fda4af}</style></head><body><main><h1>⚽ AVAX FUTBOL ANALİZ PRO V3</h1><p>Geliştirme sürümü — kalibre edilmemiş model</p><div class="card"><h2>Güncel maçlar</h2>{% if list_error %}<p class="error">{{ list_error }}</p>{% endif %}{% if not matches %}<p>Listelenecek maç bulunamadı.</p>{% endif %}{% for m in matches %}<button class="match" type="button" data-home="{{ m.home|e }}" data-away="{{ m.away|e }}" data-home-id="{{ m.home_id }}" data-away-id="{{ m.away_id }}" onclick="choose(this)">{{ m.home }} – {{ m.away }}<br><span class="muted">{{ m.league }} · UTC {{ m.date }}</span></button>{% endfor %}</div><div class="card"><h2>Maç analizi</h2><form method="post" id="form"><label>Ev sahibi</label><input name="home" id="home" value="{{ home|e }}" required><label>Deplasman</label><input name="away" id="away" value="{{ away|e }}" required><input type="hidden" name="home_id" id="home_id" value="{{ home_id|e }}"><input type="hidden" name="away_id" id="away_id" value="{{ away_id|e }}"><label>Ev sahibi beklenen gol</label><input type="number" step="0.01" min="0" max="10" name="hg" id="hg" value="{{ hg|e }}" required><label>Deplasman beklenen gol</label><input type="number" step="0.01" min="0" max="10" name="ag" id="ag" value="{{ ag|e }}" required><button type="submit">MAÇI ANALİZ ET</button></form><p class="muted">Maç seçilince takım adları ve mevcutsa gol tahminleri otomatik doldurulur. İstersen elle düzenleyebilirsin.</p>{% if error %}<p class="error">{{ error }}</p>{% endif %}</div>{% if stats %}<div class="card"><h2>Takım istatistikleri</h2>{% for name, data in stats %}<h3>{{ name }}</h3>{% for label, item in [('Son 5',data.last5),('Son 10',data.last10),('İç saha',data.home),('Deplasman',data.away)] %}{% if item %}<div class="result">{{ label }} ({{ item.n }} maç): Atılan {{ '%.2f'|format(item.scored) }} · Yenilen {{ '%.2f'|format(item.conceded) }}</div>{% endif %}{% endfor %}{% endfor %}</div>{% endif %}{% if results %}<div class="card"><h2>{{ home }} – {{ away }}</h2>{% for label, score in results %}<div class="result">{{ label }}: %{{ score }}</div>{% endfor %}<p class="muted">Olasılıklar bağımsız Poisson modeliyle hesaplanır. Tahminler kalibre edilmemiştir ve bahis garantisi değildir.</p></div>{% endif %}{% if skorlar %}<div class="card"><h2>⚽ En olası 3 skor</h2>{% for skor, oran in skorlar %}<div class="result">{{ skor }} — %{{ oran }}</div>{% endfor %}</div>{% endif %}</main><script>function choose(b){document.getElementById('home').value=b.dataset.home;document.getElementById('away').value=b.dataset.away;document.getElementById('home_id').value=b.dataset.homeId;document.getElementById('away_id').value=b.dataset.awayId;document.getElementById('hg').value='';document.getElementById('ag').value='';document.getElementById('hg').required=false;document.getElementById('ag').required=false;document.getElementById('form').submit()}</script></body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    matches, list_error = fixtures()
    values = {k: '' for k in ('home','away','home_id','away_id','hg','ag')}
    results = skorlar = stats = error = None
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
                results, skorlar = probabilities(h, a)
            except ValueError:
                error = 'Gol değerleri 0 ile 10 arasında olmalıdır.'
    return render_template_string(PAGE, matches=matches, list_error=list_error, results=results, skorlar=skorlar, stats=stats, error=error, **values)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
