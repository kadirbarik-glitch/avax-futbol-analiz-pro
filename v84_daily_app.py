"""AVAX V8.4 - Daily Football Match Center.

Standalone development application.
Does not change the live V8.3 application.
"""

from datetime import date, timedelta

from flask import Flask, render_template_string, request

from v84_daily_fixtures import (
    DailyFixtureError,
    get_daily_fixtures,
    today_turkey,
    validate_date,
)

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1">
<title>AVAX V8.4 - Günlük Maç Merkezi</title>
<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    background: #0f172a;
    color: #f8fafc;
    font-family: Arial, sans-serif;
}

.container {
    max-width: 1000px;
    margin: auto;
    padding: 20px 14px;
}

h1 {
    color: #4ade80;
    font-size: 28px;
    line-height: 1.25;
}

.subtitle {
    color: #cbd5e1;
    line-height: 1.6;
}

.panel {
    background: #1e293b;
    padding: 20px;
    border-radius: 16px;
    margin-top: 20px;
}

.filters {
    display: grid;
    grid-template-columns: repeat(
        auto-fit, minmax(180px, 1fr)
    );
    gap: 12px;
}

label {
    display: block;
    margin-bottom: 7px;
    font-weight: bold;
}

select, input, button {
    width: 100%;
    padding: 13px;
    border-radius: 9px;
    border: 1px solid #475569;
    font-size: 16px;
}

select, input {
    background: #334155;
    color: white;
}

button {
    background: #22c55e;
    color: #052e16;
    font-weight: bold;
    border: none;
    cursor: pointer;
}

.quick {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 14px;
}

.quick a {
    color: #86efac;
    text-decoration: none;
    border: 1px solid #475569;
    padding: 10px 15px;
    border-radius: 9px;
}

.stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 20px;
}

.stat {
    background: #334155;
    padding: 15px 8px;
    border-radius: 12px;
    text-align: center;
}

.stat strong {
    display: block;
    font-size: 25px;
    color: #4ade80;
}

.stat span {
    font-size: 12px;
    color: #cbd5e1;
}

.match {
    background: #334155;
    border-radius: 12px;
    padding: 15px;
    margin-top: 12px;
}

.match-header {
    color: #cbd5e1;
    font-size: 13px;
    margin-bottom: 10px;
}

.teams {
    font-size: 17px;
    font-weight: bold;
    line-height: 1.5;
}

.time {
    color: #86efac;
    margin-top: 8px;
}

.status {
    color: #cbd5e1;
    font-size: 12px;
    margin-top: 6px;
}

.warning {
    background: #422006;
    color: #fde68a;
    padding: 14px;
    border-radius: 10px;
    margin-top: 16px;
}

.empty {
    color: #cbd5e1;
    padding: 20px 0;
}

footer {
    color: #94a3b8;
    font-size: 12px;
    margin-top: 25px;
    line-height: 1.6;
}
</style>
</head>
<body>
<div class="container">

<h1>⚽ AVAX FUTBOL ANALİZ PRO V8.4</h1>
<p class="subtitle">
Günlük Maç Merkezi — Dünya genelindeki
erişilebilir futbol karşılaşmaları.
</p>

<div class="panel">
<form method="get" action="/">

<div class="filters">
<div>
<label for="date">Maç tarihi</label>
<input id="date" type="date"
       name="date" value="{{ selected }}"
       min="{{ today }}"
       max="{{ max_date }}">
</div>

<div>
<label for="country">Ülke</label>
<select id="country" name="country">
<option value="">Tüm ülkeler</option>
{% for country in countries %}
<option value="{{ country }}"
 {% if country == selected_country %}selected{% endif %}>
{{ country }}
</option>
{% endfor %}
</select>
</div>

<div>
<label for="league">Lig</label>
<select id="league" name="league">
<option value="">Tüm ligler</option>
{% for league in leagues %}
<option value="{{ league }}"
 {% if league == selected_league %}selected{% endif %}>
{{ league }}
</option>
{% endfor %}
</select>
</div>
</div>

<div style="margin-top:15px">
<button type="submit">MAÇLARI GÖSTER</button>
</div>
</form>

<div class="quick">
<a href="/?date={{ today }}">Bugün</a>
<a href="/?date={{ tomorrow }}">Yarın</a>
<a href="/?date={{ week_date }}">7 gün sonrası</a>
</div>
</div>

{% if error %}
<div class="warning">{{ error }}</div>
{% endif %}

<div class="stats">
<div class="stat">
<strong>{{ matches|length }}</strong>
<span>Listelenen maç</span>
</div>
<div class="stat">
<strong>{{ country_count }}</strong>
<span>Ülke</span>
</div>
<div class="stat">
<strong>{{ league_count }}</strong>
<span>Lig</span>
</div>
</div>

<div class="panel">
<h2>📅 {{ selected }} Maçları</h2>

{% for match in matches %}
<div class="match">
<div class="match-header">
{{ match.country }} / {{ match.league }}
</div>

<div class="teams">
{{ match.home_team }} - {{ match.away_team }}
</div>

<div class="time">
{{ match.kickoff_tr[11:16] }} (Türkiye saati)
</div>

<div class="status">
Durum: {{ match.status }}
</div>
</div>
{% else %}
<div class="empty">
Bu tarih ve filtreler için gösterilecek maç bulunamadı.
</div>
{% endfor %}
</div>

<footer>
V8.4 geliştirme sürümü.
Maç listesi API-Football verilerine bağlıdır.
Tüm organizasyonların kapsandığı garanti edilmez.
Tahmin ve bahis tavsiyesi içermez.
</footer>

</div>
</body>
</html>
"""


@app.route("/")
def daily_home():
    today = today_turkey()
    tomorrow = today + timedelta(days=1)
    week_date = today + timedelta(days=7)
    max_date = today + timedelta(days=30)

    selected_raw = request.args.get(
        "date", today.isoformat()
    )

    selected_country = request.args.get(
        "country", ""
    ).strip()

    selected_league = request.args.get(
        "league", ""
    ).strip()

    error = None
    all_matches = []

    try:
        selected_date = validate_date(selected_raw)

        if not today <= selected_date <= max_date:
            raise ValueError(
                "Tarih desteklenen araligin disinda."
            )

        result = get_daily_fixtures(selected_date)
        all_matches = result["matches"]

    except (ValueError, DailyFixtureError) as exc:
        error = str(exc)
        selected_date = today

    countries = sorted({
        m["country"] for m in all_matches
        if m.get("country")
    })

    leagues = sorted({
        m["league"] for m in all_matches
        if m.get("league")
        and (
            not selected_country
            or m.get("country") == selected_country
        )
    })

    matches = [
        m for m in all_matches
        if (
            not selected_country
            or m.get("country") == selected_country
        )
        and (
            not selected_league
            or m.get("league") == selected_league
        )
    ]

    country_count = len({
        m["country"] for m in matches
    })

    league_count = len({
        (m["country"], m["league"])
        for m in matches
    })

    return render_template_string(
        PAGE,
        selected=selected_date.isoformat(),
        today=today.isoformat(),
        tomorrow=tomorrow.isoformat(),
        week_date=week_date.isoformat(),
        max_date=max_date.isoformat(),
        countries=countries,
        leagues=leagues,
        selected_country=selected_country,
        selected_league=selected_league,
        matches=matches,
        country_count=country_count,
        league_count=league_count,
        error=error,
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5084,
        debug=False,
    )
