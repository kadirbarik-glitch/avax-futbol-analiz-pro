"""AVAX FUTBOL ANALIZ PRO V8.2 - Web Panel.

Six competitions, Turkish kickoff times,
competition/team freshness and data sufficiency.
"""

import os
from datetime import timedelta, timezone

from flask import request, render_template_string

from app_v3 import app, api_get
from v8_data import analyze_match
from v8_live_engine import parse_date
from v8_models import MODEL_SELECTIONS

V8_VERSION = "8.2-beta"
TR_TIMEZONE = timezone(timedelta(hours=3))

DEFAULT_LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "CL": "UEFA Champions League",
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

SUFFICIENCY_LABELS = {
    "INSUFFICIENT": "Yetersiz veri",
    "LOW": "Az veri",
    "MODERATE": "Orta duzey veri",
    "ADEQUATE": "Daha kapsamli veri",
}

PAGE_V8 = """
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport"
 content="width=device-width,initial-scale=1">
<title>AVAX FUTBOL ANALIZ PRO V8.2</title>
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
button:disabled {
 opacity:.45;cursor:not-allowed;
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
.info {
 background:#334155;
 border-radius:9px;
 padding:12px;
 margin:10px 0;
}
.warning {
 color:#fbbf24;
}
.team-grid {
 display:grid;
 grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
 gap:12px;
}
.team-card {
 background:#334155;
 border-radius:12px;
 padding:15px;
}
.team-card h3 {
 margin-top:0;color:#86efac;
}
.team-card p {
 margin:9px 0;font-size:14px;
}
.quality {
 border:1px solid #fbbf24;
 border-radius:10px;
 padding:14px;
 margin:14px 0;
 color:#fde68a;
}
</style>
</head>
<body>
<main>
<h1>AVAX FUTBOL ANALIZ PRO V8.2</h1>
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
{% if code in supported %}(V8.2){% endif %}
</option>
{% endfor %}
</select>
<noscript>
<button type="submit">Maclari getir</button>
</noscript>
</form>

{% if selected_league not in supported %}
<p class="muted">
Bu lig icin model henuz dogrulanmadi.
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
({{ match.turkey_time }} TSI)
</option>
{% endfor %}
</select>

<button type="submit"
{% if not matches or selected_league not in supported %}
disabled{% endif %}>
V8.2 ANALIZ ET
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
<h2>V8.2 tahmin sonuclari</h2>
{% for label, key in labels %}
<div class="result">
<span>{{ label }}</span>
<strong>
%{{ result.probabilities_percent[key] }}
</strong>
</div>
{% endfor %}

<div class="quality">
<strong>Veri yeterliligi uyarisi</strong>
<p>{{ result.data_quality_warning }}</p>
</div>
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

<div class="card">
<h2>Veri guncelligi</h2>
<div class="info">
<strong>Veri kaynagi:</strong>
{{ result.data_source }}
</div>
<div class="info">
<strong>Yuklenen gecmis mac:</strong>
{{ result.historical_matches_loaded }}
</div>
<div class="info">
<strong>Son gecmis mac:</strong>
{{ result.latest_match_tr }}
</div>
<div class="info">
<strong>Son mac ile tahmin maci arasi:</strong>
{{ result.days_since_latest }} gun
</div>
<div class="info">
<strong>Veri durumu:</strong>
{{ result.freshness_status }}
</div>
<p class="{% if result.freshness_status == 'STALE' %}warning{% else %}muted{% endif %}">
{{ result.freshness_message }}
</p>
</div>

<div class="card">
<h2>Takim bazli veri kontrolu</h2>
<div class="team-grid">
{% for team in team_details %}
<div class="team-card">
<h3>{{ team.name }}</h3>

<p>
<strong>Gecmis mac:</strong>
{{ team.matches }}
</p>

<p>
<strong>Son mac:</strong>
{{ team.latest_match_tr }}
</p>

<p>
<strong>Veri yasi:</strong>
{% if team.days_since_latest is not none %}
{{ team.days_since_latest }} gun
{% else %}
Bilinmiyor
{% endif %}
</p>

<p>
<strong>Veri durumu:</strong>
{{ team.freshness_status }}
</p>

<p class="{% if team.sufficiency_level in ['LOW', 'INSUFFICIENT'] %}warning{% endif %}">
<strong>Veri yeterliligi:</strong>
{{ team.sufficiency_label }}
</p>

<p class="muted">
{{ team.sufficiency_message }}
</p>
</div>
{% endfor %}
</div>
<p class="muted">
Takim verileri sadece secilen yarismanin
mevcut sezonundaki maclari kapsar.
Veri yeterliligi esikleri uyarilardir;
kalibre edilmis guven puanlari degildir.
</p>
</div>
{% endif %}

<div class="card">
<p class="muted">
V8.2 olasiliklari deneysel sonuclardir.
Skor, ilk yari ve ikinci yari tahminleri
mevcut V3 ekraninda bulunur.
</p>
<a href="/">V3 analiz ekranina don</a>
</div>
</main>
</body>
</html>
"""


def turkey_time(value):
    dt = parse_date(value)
    return dt.astimezone(
        TR_TIMEZONE
    ).strftime("%d.%m.%Y %H:%M")


def get_leagues():
    data, error = api_get("/competitions")
    leagues = DEFAULT_LEAGUES.copy()

    if error or not isinstance(data, dict):
        return leagues

    for item in data.get("competitions", []):
        if not isinstance(item, dict):
            continue

        code = item.get("code")
        name = item.get("name")

        if code and name:
            leagues[code] = name

    return leagues


@app.get("/v8/status")
def avax_v8_status():
    return {
        "application": "AVAX FUTBOL ANALIZ PRO",
        "version": V8_VERSION,
        "status": "beta",
        "supported_leagues": list(MODEL_SELECTIONS),
        "live_odds_included": False,
    }


@app.route("/v8", methods=["GET", "POST"])
def avax_v8_panel():
    leagues = get_leagues()

    league = str(
        request.values.get("league", "PL")
    ).upper()

    if league not in leagues:
        league = "PL"

    data, list_error = api_get(
        f"/competitions/{league}/matches"
        "?status=SCHEDULED"
    )

    matches = []

    if isinstance(data, dict):
        for match in data.get("matches", []):
            if not isinstance(match, dict):
                continue

            home = match.get("homeTeam") or {}
            away = match.get("awayTeam") or {}

            if (
                match.get("id") is not None
                and match.get("utcDate")
                and home.get("id") is not None
                and away.get("id") is not None
            ):
                match = match.copy()

                try:
                    match["turkey_time"] = turkey_time(
                        match["utcDate"]
                    )
                except (ValueError, TypeError):
                    continue

                matches.append(match)

    matches.sort(
        key=lambda m: (
            parse_date(m["utcDate"]),
            m["id"],
        )
    )
    matches = matches[:100]

    result = None
    error = None
    team_details = []

    selected_match = request.form.get(
        "match_id", ""
    )

    if request.method == "POST":
        if league not in MODEL_SELECTIONS:
            error = (
                "Bu lig icin model "
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

                    latest = result.get(
                        "latest_match_utc"
                    )

                    result["latest_match_tr"] = (
                        turkey_time(latest)
                        if latest else "Bilinmiyor"
                    )

                    for key, name in (
                        (
                            "home_team_freshness",
                            match["homeTeam"]["name"],
                        ),
                        (
                            "away_team_freshness",
                            match["awayTeam"]["name"],
                        ),
                    ):
                        info = result.get(key, {}).copy()
                        latest_team = info.get(
                            "latest_match_utc"
                        )

                        info["name"] = name
                        info["latest_match_tr"] = (
                            turkey_time(latest_team)
                            if latest_team
                            else "Bilinmiyor"
                        )

                        level = info.get(
                            "sufficiency_level",
                            "INSUFFICIENT",
                        )

                        info["sufficiency_label"] = (
                            SUFFICIENCY_LABELS.get(
                                level, level
                            )
                        )

                        team_details.append(info)

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
        team_details=team_details,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
    )
