from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def ana_sayfa():
    return render_template_string(from flask import Flask, request, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AVAX FUTBOL ANALİZ PRO</title>
<style>
body {
 background:#101827; color:white;
 font-family:Arial,sans-serif;
 margin:0; padding:20px;
}
main {max-width:650px;margin:auto}
h1 {text-align:center;color:#54d9b1}
.card {
 background:#1d293b;padding:20px;
 border-radius:14px;margin:18px 0;
}
input,button {
 width:100%;box-sizing:border-box;
 padding:13px;margin:7px 0 15px;
 border-radius:8px;border:0;font-size:16px;
}
button {background:#22c55e;color:#07130b;font-weight:bold}
.result {padding:12px;border-bottom:1px solid #405064}
small {color:#bac5d5}
</style>
</head>
<body>
<main>
<h1>⚽ AVAX FUTBOL ANALİZ PRO</h1>
<p style="text-align:center">Futbol Analiz Merkezi</p>
<div class="card">
<form method="post">
<label>Ev sahibi takım</label>
<input name="home" required value="{{ home }}">
<label>Deplasman takımı</label>
<input name="away" required value="{{ away }}">
<label>Ev sahibi son 5 maç gol ortalaması</label>
<input type="number" name="hg" min="0" max="10"
 step="0.1" value="{{ hg }}" required>
<label>Deplasman son 5 maç gol ortalaması</label>
<input type="number" name="ag" min="0" max="10"
 step="0.1" value="{{ ag }}" required>
<button type="submit">MAÇI ANALİZ ET</button>
</form>
</div>
{% if result %}
<div class="card">
<h2>{{ home }} - {{ away }}</h2>
<div class="result">Ev sahibi eğilim puanı: {{ result[0] }}/100</div>
<div class="result">Beraberlik eğilim puanı: {{ result[1] }}/100</div>
<div class="result">Deplasman eğilim puanı: {{ result[2] }}/100</div>
<div class="result">2,5 Üst eğilim puanı: {{ result[3] }}/100</div>
<div class="result">2,5 Alt eğilim puanı: {{ result[4] }}/100</div>
<div class="result">Karşılıklı gol eğilim puanı: {{ result[5] }}/100</div>
<p><small>Bu puanlar basit bir prototip hesabıdır.
Gerçek bahis olasılığı veya garanti tahmin değildir.</small></p>
</div>
{% endif %}
</main>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    home = away = ""
    hg = ag = ""
    result = None

    if request.method == "POST":
        home = request.form.get("home", "").strip()
        away = request.form.get("away", "").strip()
        hg = request.form.get("hg", "")
        ag = request.form.get("ag", "")
        try:
            h = max(0, min(10, float(hg)))
            a = max(0, min(10, float(ag)))
            total = h + a
            home_score = round(100 * h / total) if total else 50
            away_score = 100 - home_score
            draw_score = round(100 * max(0, 1 - abs(h-a)/5))
            over = round(100 * total / (total + 2.5))
            under = 100 - over
            btts = round(100 * min(h,a) / (min(h,a)+1))
            result = [
                home_score, draw_score, away_score,
                over, under, btts
            ]
        except ValueError:
            pass

    return render_template_string(
        HTML, home=home, away=away,
        hg=hg, ag=ag, result=result
    )
""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>AVAX FUTBOL ANALİZ PRO</title>
    </head>
    <body style="background:#101827;color:white;
                 font-family:Arial;text-align:center;
                 padding:40px 15px;">
        <h1>⚽ AVAX FUTBOL ANALİZ PRO</h1>
        <h2>Futbol Analiz Merkezi</h2>
        <p>Program başarıyla çalışıyor.</p>
        <p>Maç analiz sistemi hazırlanıyor.</p>
    </body>
    </html>
    """)
