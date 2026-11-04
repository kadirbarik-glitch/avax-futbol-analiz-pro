"""AVAX V8 - Dinamik lig ve mac secimi."""

import os
from flask import request, render_template_string
from app_v3 import app, api_get
from v8_data import analyze_match
from v8_models import MODEL_SELECTIONS

V8_VERSION = "8.1-beta"

DEFAULT_LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
}

LABELS = [
    ("Ev sahibi kazanir", "home"),
    ("Beraberlik", "draw"),
    ("Deplasman kazanir", "away"),
    ("2.5 Ust", "over25"),
    ("2.5 Alt", "under25"),
    ("KG Var", "btts"),
    ("KG Yok", "no_btts"),
]

PAGE_V8 = """
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport"
 content="width=device-width,initial-scale=1">
<title>AVAX FUTBOL ANALIZ PRO V8</title>
<style>
body {
 margin:0;padding:16px;background:#0f172a;
 color:#f8fafc;font:16px Arial,sans-serif;
}
main {max-width:760px;margin:auto}
h1 {color:#4ade80;font-size:27px}
.card {
 background:#1e293b;border-radius:14px;
 padding:18px;margin:14px 0;
}
button,select {
 width:100%;padding:13px;margin:8px 0;
 border:0;border-radius:9px;font-size:16px;
}
button {
 background:#22c55e;color:#052e16;
 font-weight:bold;cursor:pointer;
}
select {background:#334155;color:white}
.result {
 display:flex;justify-content:space-between;
 gap:12px;padding:12px 0;
 border-bottom:1px solid #475569;
}
.error {color:#fda4af}
.muted {color:#cbd5e1;font-size:13px}
a {color:#86efac}
</style>
</head>
<body>
<main>
<h1>AVAX FUTBOL ANALIZ PRO V8</h1>
<p class="muted">
Deneysel futbol tahminleri.
Garanti veya bahis tavsiyesi degildir.
</p>

<div class="card">
<h2>Gunluk mac analizi</h2>

<form method="get" action="/v8">
<label for="league">Lig sec</label>
<select id="league" name="league"
 onchange="this.form.submit()">
{% for code, name in leagues.items() %}
<option value="{{ code }}"
{% if code == selected_league %}selected{% endif %}>
{{ name }}
{% if code in supported %}(V8){% endif %}
</option>
{% endfor %}
</select>
<noscript>
<button type="submit">Maclari getir</button>
</noscript>
</form>

{% if selected_league not in supported %}
<p class="muted">
Bu ligde V8 modeli henuz dogrulanmadi.
Maclar goruntulenebilir, tahmin uretilmez.
</p>
{% endif %}

<form method="post" action="/v8">
<input type="hidden" name="league"
 value="{{ selected_league }}">
<label for="match_id">Mac sec</label>
<select id="match_id" name="match_id">
{% for match in matches %}
<option value="{{ match.id }}"
{% if match.id|string == selected_match|string %}
selected{% endif %}>
{{ match.homeTeam.name }} -
{{ match.awayTeam.name }}
({{ match.utcDate[:16] }})
</option>
{% endfor %}
</select>
<button type="submit"
{% if not matches or selected_league not in supported %}
disabled{% endif %}>
V8 ANALIZ ET
</button>
</form>

{% if list_error %}
<p class="error">{{ list_error }}</p>
{% endif %}
{% if not matches %}
<p class="muted">
Bu lig icin planlanmis mac bulunamadi.
</p>
{% endif %}
</div>

{% if error %}
<div class="card">
<p class="error">{{ error }}</p>
</div>
{% endif %}

{% if result %}
<div class="card">
<h2>V8 tahmin sonuclari</h2>
{% for label, key in labels %}
<div class="result">
<span>{{ label }}</span>
<strong>
%{{ result.probabilities_percent[key] }}
</strong>
</div>
{% endfor %}
</div>

<div class="card">
<h2>Kullanilan modeller</h2>
{% for market, info in result.models.items() %}
<div class="result">
<span>{{ market }}</span>
<strong>{{ info.model }}</strong>
</div>
{% endfor %}
<p class="muted">
Gecmis mac sayisi:
{{ result.matches_in_history }}
</p>
</div>
{% endif %}

<div class="card">
<p class="muted">
V8 olasiliklari deneysel sonuclardir.
Skor, ilk yari ve ikinci yari tahminleri
mevcut V3 ekraninda bulunur.
</p>
<a href="/">V3 analiz ekranina don</a>
</div>
</main>
</body>
</html>
"""


def get_leagues():
    data, error = api_get("/competitions")

    if error or not isinstance(data, dict):
        return DEFAULT_LEAGUES.copy()

    competitions = data.get("competitions", [])
    leagues = {}

    for item in competitions:
        code = item.get("code")
        name = item.get("name")
        if code and name:
            leagues[code] = name

    return leagues or DEFAULT_LEAGUES.copy()


@app.get("/v8/status")
def avax_v8_status():
    return {
        "application": "AVAX FUTBOL ANALIZ PRO",
        "version": V8_VERSION,
        "status": "beta",
        "v8_model_integrated": True,
        "live_odds_included": False,
    }


@app.route("/v8", methods=["GET", "POST"])
def avax_v8_panel():
    leagues = get_leagues()

    league = request.values.get("league", "PL")

    if league not in leagues:
        league = next(iter(leagues))

    data, list_error = api_get(
        f"/competitions/{league}/matches"
        "?status=SCHEDULED"
    )

    matches = []
    if isinstance(data, dict):
        matches = [
            m for m in data.get("matches", [])
            if m.get("id")
            and m.get("utcDate")
            and (m.get("homeTeam") or {}).get("id")
            and (m.get("awayTeam") or {}).get("id")
        ][:100]

    result = None
    error = None
    selected_match = request.form.get("match_id", "")

    if request.method == "POST":
        if league not in MODEL_SELECTIONS:
            error = (
                "Bu lig icin V8 modeli "
                "henuz dogrulanmadi."
            )
        else:
            match = next(
                (
                    m for m in matches
                    if str(m["id"]) == selected_match
                ),
                None,
            )

            if match is None:
                error = "Secilen mac bulunamadi."
            else:
                try:
                    result = analyze_match(
                        league,
                        match["homeTeam"]["id"],
                        match["awayTeam"]["id"],
                        match["utcDate"],
                    )
                except (
                    ValueError,
                    RuntimeError,
                    TypeError,
                    KeyError,
                ) as exc:
                    error = str(exc)

    return render_template_string(
        PAGE_V8,
        leagues=leagues,
        supported=MODEL_SELECTIONS,
        selected_league=league,
        selected_match=selected_match,
        matches=matches,
        list_error=list_error,
        result=result,
        error=error,
        labels=LABELS,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
    )
