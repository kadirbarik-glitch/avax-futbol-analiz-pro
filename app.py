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
        return None, f'Veri servisi HTTP {exc.code} hatası verdi. Lig veya takım paketinizde bulunmayabilir.'
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
            matches.append({'id': item.get('id'), 'home': home.get('name', ''), 'away': away.get('name', ''),
                            'home_id': home['id'], 'away_id': away['id'],
                            'date': (item.get('utcDate') or '')[:16].replace('T', ' '),
                            'league': (item.get('competition') or {}).get('name', '')})
    return matches, None

def team_stats(team_id, venue=None):
    """Son 30 maçtan atılan/yenen gol; devre verisi varsa ayrıca hesapla."""
    data, err = api_get(f'/teams/{int(team_id)}/matches?status=FINISHED&limit=30')
    if err:
        return None, err
    rows = []
    for match in data.get('matches', []):
        home = (match.get('homeTeam') or {}).get('id') == team_id
        away = (match.get('awayTeam') or {}).get('id') == team_id
        if not (home or away) or (venue == 'home' and not home) or (venue == 'away' and not away):
            continue
        score = match.get('score') or {}
        ft = score.get('fullTime') or {}
        ht = score.get('halfTime') or {}
        gf = ft.get('home' if home else 'away')
        ga = ft.get('away' if home else 'home')
        if not isinstance(gf, int) or not isinstance(ga, int):
            continue
        hf = ht.get('home' if home else 'away')
        ha = ht.get('away' if home else 'home')
        rows.append((gf, ga, hf, ha))
    if len(rows) < 3:
        return None, 'Bu takım için en az 3 tamamlanmış maç verisi gerekli.'
    stats = {'count': len(rows), 'for': sum(x[0] for x in rows)/len(rows),
             'against': sum(x[1] for x in rows)/len(rows)}
    half = [x for x in rows if isinstance(x[2], int) and isinstance(x[3], int)]
    if len(half) >= 3:
        stats['half_count'] = len(half)
        stats['half_for'] = sum(x[2] for x in half)/len(half)
        stats['half_against'] = sum(x[3] for x in half)/len(half)
    return stats, None


def recent_goals(team_id):
    stats, err = team_stats(team_id)
    return (stats['for'] if stats else None), err


def enhanced_stats(home_id, away_id):
    hs, he = team_stats(home_id, 'home')
    aws, ae = team_stats(away_id, 'away')
    if he or ae:
        return None, '; '.join(dict.fromkeys(x for x in (he, ae) if x))
    h = (hs['for'] + aws['against']) / 2
    a = (aws['for'] + hs['against']) / 2
    output = {'home': hs, 'away': aws, 'h': h, 'a': a}
    if 'half_for' in hs and 'half_for' in aws:
        hh = (hs['half_for'] + aws['half_against']) / 2
        ah = (aws['half_for'] + hs['half_against']) / 2
        output['half'] = predictions(hh, ah)
        output['second'] = predictions(max(0, h-hh), max(0, a-ah))
    return output, None


def top_scores(h, a):
    vals = [(f'{i}-{j}', poisson(i,h)*poisson(j,a)) for i in range(11) for j in range(11)]
    return [(name, round(prob*100, 1)) for name, prob in sorted(vals, key=lambda x: x[1], reverse=True)[:3]]

def poisson(k, mean):
    return exp(-mean) * mean ** k / factorial(k)

def predictions(h, a):
    result = {'home': 0., 'draw': 0., 'away': 0., 'over': 0., 'btts': 0.}
    for i in range(21):
        for j in range(21):
            p = poisson(i, h) * poisson(j, a)
            result['home' if i > j else 'draw' if i == j else 'away'] += p
            if i + j > 2:
                result['over'] += p
            if i and j:
                result['btts'] += p
    return [(label, round(value * 100, 1)) for label, value in [
        ('Ev sahibi kazanır', result['home']), ('Beraberlik', result['draw']),
        ('Deplasman kazanır', result['away']), ('2,5 Üst', result['over']),
        ('2,5 Alt', 1-result['over']), ('Karşılıklı gol VAR', result['btts'])]]

PAGE = '''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVAX FUTBOL ANALİZ PRO</title>
<style>body{font:16px Arial;background:#101827;color:#f1f5f9;margin:0;padding:16px}main{max-width:720px;margin:auto}h1{color:#4ade80}.card{background:#1e293b;border-radius:14px;padding:18px;margin:15px 0}button,input{box-sizing:border-box;font:inherit;padding:12px;border-radius:8px;border:0}button{background:#22c55e;color:#052e16;cursor:pointer}input{width:100%;margin:7px 0 14px}label{display:block}.match{display:block;width:100%;text-align:left;margin:7px 0;background:#334155;color:white}.muted{color:#cbd5e1;font-size:13px}.result{padding:9px;border-bottom:1px solid #475569}.error{color:#fda4af}</style></head><body><main><h1>⚽ AVAX FUTBOL ANALİZ PRO</h1><p>Futbol Analiz Merkezi</p>
<div class="card"><h2>Güncel maçlar</h2>{% if list_error %}<p class="error">{{ list_error }}</p>{% endif %}{% if not matches %}<p>Listelenecek maç bulunamadı.</p>{% endif %}{% for m in matches %}<button class="match" type="button" data-home="{{ m.home|e }}" data-away="{{ m.away|e }}" data-home-id="{{ m.home_id }}" data-away-id="{{ m.away_id }}" onclick="choose(this)">{{ m.home }} – {{ m.away }}<br><span class="muted">{{ m.league }} · UTC {{ m.date }}</span></button>{% endfor %}</div>
<div class="card"><h2>Maç analizi</h2><form method="post" id="form"><label>Ev sahibi</label><input name="home" id="home" value="{{ home|e }}" required><label>Deplasman</label><input name="away" id="away" value="{{ away|e }}" required><input type="hidden" name="home_id" id="home_id" value="{{ home_id|e }}"><input type="hidden" name="away_id" id="away_id" value="{{ away_id|e }}"><label>Ev sahibi beklenen gol</label><input type="number" step="0.01" min="0" max="10" name="hg" id="hg" value="{{ hg|e }}" required><label>Deplasman beklenen gol</label><input type="number" step="0.01" min="0" max="10" name="ag" id="ag" value="{{ ag|e }}" required><button type="submit">MAÇI ANALİZ ET</button></form><p class="muted">Bir maç seçince takım adları doldurulur. Otomatik istatistik bulunursa gol ortalamaları da gelir; aksi halde elle girilebilir.</p>{% if error %}<p class="error">{{ error }}</p>{% endif %}</div>
{% if results %}<div class="card"><h2>{{ home }} – {{ away }}</h2>{% for label, score in results %}<div class="result">{{ label }}: {{ score }}%</div>{% endfor %}<p class="muted">Poisson modeliyle hesaplanmış, kalibre edilmemiş tahminlerdir. Son maçlardaki atılan gol ortalaması gerçek beklenen gol (xG) değildir. Savunma gücü, sakatlık ve saha avantajı ayrıca modellenmez. Bahis garantisi yoktur.</p></div>{% endif %}
{% if advanced %}<div class="card"><h2>Gelişmiş takım analizi</h2>
<p>Ev sahibi iç saha: {{ advanced.home.count }} maç; attığı {{ '%.2f'|format(advanced.home['for']) }}, yediği {{ '%.2f'|format(advanced.home.against) }} gol/maç</p>
<p>Deplasman dış saha: {{ advanced.away.count }} maç; attığı {{ '%.2f'|format(advanced.away['for']) }}, yediği {{ '%.2f'|format(advanced.away.against) }} gol/maç</p>
{% if advanced.half %}<h3>İlk yarı (model)</h3>{% for label, pct in advanced.half %}<div class="result">{{ label }}: %{{ pct }}</div>{% endfor %}
<h3>İkinci yarı (model)</h3>{% for label, pct in advanced.second %}<div class="result">{{ label }}: %{{ pct }}</div>{% endfor %}
{% else %}<p class="muted">Yeterli devre skoru verisi bulunamadı; yarı tahminleri gösterilmiyor.</p>{% endif %}
<p class="muted">Basit hücum-savunma ortalaması ve bağımsız Poisson varsayımı. Kalibre edilmemiş tahminlerdir, xG değildir ve bahis garantisi vermez.</p></div>{% endif %}
{% if scores %}<div class="card"><h2>En olası 3 skor</h2>{% for name, pct in scores %}<div class="result">{{ name }}: %{{ pct }}</div>{% endfor %}</div>{% endif %}
</main><script>function choose(b){document.getElementById('home').value=b.dataset.home;document.getElementById('away').value=b.dataset.away;document.getElementById('home_id').value=b.dataset.homeId;document.getElementById('away_id').value=b.dataset.awayId;document.getElementById('hg').value='';document.getElementById('ag').value='';document.getElementById('form').requestSubmit()}</script></body></html>'''

@app.route('/', methods=['GET', 'POST'])
def index():
    matches, list_error = fixtures()
    values = {k: '' for k in ('home','away','home_id','away_id','hg','ag')}
    results = None
    scores = None
    advanced = None
    error = None
    if request.method == 'POST':
        values = {k: request.form.get(k, '').strip() for k in values}
        try:
            home_id, away_id = int(values['home_id']), int(values['away_id'])
        except (ValueError, TypeError):
            home_id = away_id = None
        if home_id and away_id:
            advanced, stat_error = enhanced_stats(home_id, away_id)
            if advanced and (not values['hg'] or not values['ag']):
                values['hg'], values['ag'] = str(round(advanced['h'], 2)), str(round(advanced['a'], 2))
            elif stat_error and (not values['hg'] or not values['ag']):
                error = 'Gelişmiş otomatik veri alınamadı: ' + stat_error + ' İstersen gol ortalamalarını elle girebilirsin.'
        if values['hg'] and values['ag']:
            try:
                h, a = float(values['hg']), float(values['ag'])
                if not (0 <= h <= 10 and 0 <= a <= 10):
                    raise ValueError()
                results = predictions(h, a)
                scores = top_scores(h, a)
            except ValueError:
                error = 'Gol ortalamaları 0 ile 10 arasında olmalıdır.'
    return render_template_string(PAGE, matches=matches, list_error=list_error, results=results, scores=scores, advanced=advanced, error=error, **values)
