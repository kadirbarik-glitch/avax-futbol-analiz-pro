from mac_verileri import maclari_getir
from flask import Flask, request, render_template_string
from math import exp, factorial

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
 background:#101827;
 color:white;
 font-family:Arial,sans-serif;
 padding:18px;
}
main {max-width:600px;margin:auto}
h1 {color:#4ade80;text-align:center}
.card {
 background:#1e293b;
 padding:20px;
 border-radius:14px;
 margin:18px 0;
}
input,button {
 box-sizing:border-box;
 width:100%;
 padding:13px;
 margin:8px 0 16px;
 border:0;
 border-radius:8px;
 font-size:16px;
}
button {
 background:#22c55e;
 color:#052e16;
 font-weight:bold;
}
.result {
 padding:12px;
 border-bottom:1px solid #475569;
}
small {color:#cbd5e1}
</style>
</head>
<body>
<main>
<h1>⚽ AVAX FUTBOL ANALİZ PRO</h1>
<p style="text-align:center">Futbol Analiz Merkezi</p>
<div class="card">
<h2>⚽ Güncel Maçlar</h2>
{% for mac in maclar %}
<p>{{ mac.ev }} - {{ mac.deplasman }}</p>
{% endfor %}
<form method="post">
<label>Ev sahibi takım</label>
<input name="home" value="{{ home }}" required>
<label>Deplasman takımı</label>
<input name="away" value="{{ away }}" required>
<label>Ev sahibi beklenen gol ortalaması</label>
<input type="number" name="hg" min="0" max="10"
 step="0.1" value="{{ hg }}" required>
<label>Deplasman beklenen gol ortalaması</label>
<input type="number" name="ag" min="0" max="10"
 step="0.1" value="{{ ag }}" required>
<button type="submit">MAÇI ANALİZ ET</button>
</form>
</div>
{% if result %}
<div class="card">
<h2>{{ home }} - {{ away }}</h2>
{% for label, value in result %}
<div class="result">
{{ label }}: {{ value }}%
</div>
{% endfor %}
<p><small>
Bu hesaplama Poisson gol modeline dayanır.
Girilen gol beklentileri tahmini sonuçları belirler.
Gerçek maç verileri otomatik alınmamaktadır.
Bahis kazancı garanti değildir.
</small></p>
</div>
{% endif %}
</main>
</body>
</html>
"""

def poisson(k, mean):
    return exp(-mean) * mean ** k / factorial(k)

def analiz(h, a):
    home_win = draw = away_win = 0
    over = btts = 0

    for i in range(41):
        for j in range(41):
            p = poisson(i, h) * poisson(j, a)
            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p
            if i + j >= 3:
                over += p
            if i > 0 and j > 0:
                btts += p

    return [
        ("Ev sahibi kazanır", round(home_win * 100, 1)),
        ("Beraberlik", round(draw * 100, 1)),
        ("Deplasman kazanır", round(away_win * 100, 1)),
        ("2,5 Üst", round(over * 100, 1)),
        ("2,5 Alt", round((1-over) * 100, 1)),
        ("Karşılıklı gol VAR", round(btts * 100, 1))
    ]

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
            h = float(hg)
            a = float(ag)
            if 0 <= h <= 10 and 0 <= a <= 10:
                result = analiz(h, a)
        except ValueError:
            pass

    return render_template_string(
        HTML,
        home=home,
        away=away,
        hg=hg,
        ag=ag,
        result=result,
     maclar=maclari_getir()["maclar"]
    )
