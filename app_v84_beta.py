"""Mobile-first, authenticated AVAX V8.4 beta application.

This app is intentionally separate from the V8.3 and V8.4 development
servers. It never invents a fixture or prediction: all lists come from the
football-data.org adapter and the detail view calls the guarded V8 bridge.
"""

import hmac
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, Response, abort, render_template_string, request

from v84_analysis_bridge import prepare_analysis
from v84_daily_app import classify_match, kickoff_is_past
from v84_daily_fixtures import (
    DailyFixtureError,
    get_daily_fixtures,
    today_turkey,
    validate_date,
)

app = Flask(__name__)
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True)

MODEL_COMPETITIONS = frozenset({"PL", "PD", "SA", "BL1", "FL1", "CL"})
UNSAFE_QUALITY_LEVELS = frozenset({"LOW", "INSUFFICIENT"})


def beta_credentials_configured():
    """Return whether both beta credentials are present without exposing them."""
    return bool(
        os.environ.get("BETA_USERNAME", "").strip()
        and os.environ.get("BETA_PASSWORD", "")
    )


def beta_authorized():
    username = os.environ.get("BETA_USERNAME", "").strip()
    password = os.environ.get("BETA_PASSWORD", "")
    auth = request.authorization
    return bool(
        username
        and password
        and auth
        and hmac.compare_digest(auth.username or "", username)
        and hmac.compare_digest(auth.password or "", password)
    )


def require_beta_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not beta_credentials_configured():
            return (
                "Beta authentication is not configured.",
                503,
                {"Cache-Control": "no-store"},
            )
        if not beta_authorized():
            return Response(
                "Authentication required.",
                401,
                {
                    "WWW-Authenticate": 'Basic realm="AVAX V8.4 Beta"',
                    "Cache-Control": "no-store",
                },
            )
        return view(*args, **kwargs)
    return wrapped


def selected_date_or_today(value):
    today = today_turkey()
    selected = validate_date(value or today.isoformat())
    if not today <= selected <= today + timedelta(days=30):
        raise ValueError("Tarih desteklenen aralığın dışında.")
    return selected


def load_day(value):
    selected = selected_date_or_today(value)
    return selected, get_daily_fixtures(selected)


def match_groups(matches):
    groups = {name: [] for name in ("upcoming", "live", "finished", "postponed", "other")}
    now = datetime.now(timezone.utc)
    for raw_match in matches:
        match = dict(raw_match)
        match["analysis_supported"] = (
            str(match.get("league_id", "")).upper()
            in MODEL_COMPETITIONS
        )
        match["analysis_label"] = (
            "Analiz destekleniyor"
            if match["analysis_supported"]
            else "Analiz desteklenmiyor"
        )
        group = classify_match(match.get("status", ""))
        if group == "upcoming" and kickoff_is_past(match, now):
            group = "other"
        groups[group].append(match)
    for rows in groups.values():
        rows.sort(
            key=lambda match: (
                not match["analysis_supported"],
                match.get("kickoff_tr", ""),
                match.get("match_id", ""),
            )
        )
    return groups


def prediction_display_allowed(analysis):
    """Reject display when actual history quality is too weak for beta use."""
    prediction = analysis.get("prediction") or {}
    quality = prediction.get("market_data_quality") or {}
    levels = {item.get("level") for item in quality.values()}
    freshness = {item.get("freshness") for item in quality.values()}
    return bool(
        prediction
        and quality
        and not levels.intersection(UNSAFE_QUALITY_LEVELS)
        and "NO_DATA" not in freshness
    )


def quality_warning(analysis):
    prediction = analysis.get("prediction") or {}
    quality = prediction.get("market_data_quality") or {}
    levels = sorted({item.get("level", "") for item in quality.values()})
    warning = prediction.get("data_quality_warning")
    if warning:
        return warning, ", ".join(levels) or "BİLİNMİYOR"
    return analysis.get("warning") or analysis.get("reason"), ", ".join(levels) or "VERİ YOK"


BASE_STYLE = """
<style>
:root { color-scheme: dark; --bg:#050914; --panel:#0c1629; --line:#233654; --ink:#e7f1ff; --muted:#90a8c8; --blue:#18a8ff; --cyan:#7ad7ff; --warn:#ffd36b; --danger:#ff8b98; }
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at top,#10264a 0,var(--bg) 42rem);color:var(--ink);font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif} main{max-width:720px;margin:auto;padding:18px 14px 40px}.brand{letter-spacing:.08em;color:var(--cyan);font-size:12px;font-weight:800}.title{font-size:28px;line-height:1.1;margin:6px 0}.sub,.muted{color:var(--muted);font-size:14px}.panel,.match{background:linear-gradient(145deg,rgba(18,35,63,.98),rgba(8,17,32,.98));border:1px solid var(--line);border-radius:16px;padding:15px;margin:12px 0;box-shadow:0 14px 32px rgba(0,0,0,.2)}.filters{display:grid;gap:10px;grid-template-columns:1fr auto}input,button,a.button{font:inherit;border-radius:10px;padding:11px 12px}input{min-width:0;background:#071225;color:var(--ink);border:1px solid var(--line)}button,a.button{background:var(--blue);color:#00101c;border:0;font-weight:800;text-decoration:none;display:inline-block}.quick{display:flex;gap:8px;margin-top:10px}.quick a{color:var(--cyan);font-size:13px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.summary div{background:#071225;border:1px solid var(--line);border-radius:12px;padding:10px;text-align:center}.summary strong{display:block;color:var(--cyan);font-size:20px}.label{color:var(--muted);font-size:12px}.league{color:var(--cyan);font-size:13px}.teams{font-size:18px;font-weight:750;margin:7px 0}.time{color:var(--muted);font-size:13px}.tag{float:right;border:1px solid var(--line);padding:2px 7px;border-radius:999px;font-size:11px;color:var(--muted)}.notice{border-left:3px solid var(--warn);padding:10px 12px;background:#241d0b;color:#ffe7a8;border-radius:8px;margin:12px 0}.error{border-left-color:var(--danger);background:#2a1118;color:#ffc1c9}.section{margin:26px 0 8px;font-size:17px}.prob{display:grid;grid-template-columns:1fr auto;gap:5px;padding:8px 0;border-bottom:1px solid var(--line)}.prob:last-child{border:0}.prob b{color:var(--cyan)}.back{color:var(--cyan);text-decoration:none;font-weight:700} footer{color:var(--muted);font-size:12px;margin-top:20px}@media(max-width:420px){main{padding:14px 11px}.title{font-size:25px}.filters{grid-template-columns:1fr}.filters button{width:100%}}
</style>
"""


HOME_PAGE = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVAX V8.4 Beta</title>""" + BASE_STYLE + """</head><body><main>
<div class="brand">AVAX FUTBOL ANALİZ PRO · BETA</div><h1 class="title">Günlük maç merkezi</h1><p class="sub">Canlı sağlayıcı verisi · Türkiye saati · Beta erişimi</p>
<form class="panel filters" method="get"><input type="date" name="date" value="{{ selected }}" min="{{ today }}" max="{{ max_date }}"><button>Maçları getir</button></form>
<div class="quick"><a href="/?date={{ today }}">Bugün</a><a href="/?date={{ tomorrow }}">Yarın</a></div>
{% if error %}<div class="notice error">{{ error }}</div>{% endif %}
<div class="summary"><div><strong>{{ total }}</strong><span class="label">maç</span></div><div><strong>{{ upcoming|length }}</strong><span class="label">başlamamış</span></div><div><strong>{{ live|length }}</strong><span class="label">canlı</span></div></div>
{% for heading, rows in [("Başlamamış maçlar",upcoming),("Canlı maçlar",live),("Tamamlanan maçlar",finished),("Ertelenen / diğer",postponed + other)] %}
<h2 class="section">{{ heading }} · {{ rows|length }}</h2>{% for match in rows %}<article class="match"><span class="tag">{{ match.status }}</span><div class="league">{{ match.country }} · {{ match.league }}</div><div class="teams">{{ match.home_team }} – {{ match.away_team }}</div><div class="time">{{ match.kickoff_tr[11:16] }} · Türkiye saati</div><p class="muted">{{ match.analysis_label }}</p>{% if match in upcoming %}<p><a class="button" href="/match/{{ match.match_id }}?date={{ selected }}">Detay ve analiz</a></p>{% endif %}</article>{% else %}<p class="muted">Bu grupta maç yok.</p>{% endfor %}{% endfor %}
<footer>Tahminler bilgilendirme amaçlıdır; garanti veya bahis tavsiyesi değildir.</footer></main></body></html>"""


DETAIL_PAGE = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Maç detayı · AVAX Beta</title>""" + BASE_STYLE + """</head><body><main><a class="back" href="/?date={{ selected }}">← Maç listesine dön</a><article class="panel"><div class="league">{{ match.country }} · {{ match.league }}</div><h1 class="title">{{ match.home_team }}<br>– {{ match.away_team }}</h1><p class="sub">{{ match.kickoff_tr[0:16].replace('T',' ') }} · Türkiye saati · {{ match.status }}</p></article>
<h2 class="section">Veri yeterliliği</h2><div class="notice">Seviye: <b>{{ quality_level }}</b><br>{{ quality_message }}</div>
<h2 class="section">Analiz</h2>{% if analysis.prediction %}<article class="panel"><p class="muted">{{ analysis.warning }}</p>{% for label, value in probabilities %}<div class="prob"><span>{{ label }}</span><b>%{{ value }}</b></div>{% endfor %}</article>{% else %}<div class="notice error">{{ analysis.reason }}<br><span class="muted">{{ analysis.warning }}</span></div>{% endif %}<footer>Gerçek maç ve geçmiş veri kullanılır. Örnek/sentetik tahmin gösterilmez.</footer></main></body></html>"""


@app.route("/")
@require_beta_auth
def home():
    today = today_turkey()
    try:
        selected, result = load_day(request.args.get("date"))
        groups = match_groups(result["matches"])
        error = None
    except (ValueError, DailyFixtureError) as exc:
        selected, groups, error = today, match_groups([]), str(exc)
    return render_template_string(HOME_PAGE, selected=selected.isoformat(), today=today.isoformat(), tomorrow=(today + timedelta(days=1)).isoformat(), max_date=(today + timedelta(days=30)).isoformat(), total=sum(map(len, groups.values())), error=error, **groups)


@app.route("/match/<match_id>")
@require_beta_auth
def match_detail(match_id):
    try:
        selected, result = load_day(request.args.get("date"))
    except (ValueError, DailyFixtureError) as exc:
        return render_template_string(DETAIL_PAGE, selected=today_turkey().isoformat(), match={}, analysis={"prediction": None, "reason": str(exc), "warning": "Veri servisi kullanılamıyor."}, probabilities=[], quality_level="VERİ YOK", quality_message=str(exc)), 400
    match = next((item for item in result["matches"] if item.get("match_id") == str(match_id)), None)
    if match is None:
        abort(404)
    analysis = prepare_analysis(match)
    prediction = analysis.get("prediction") or {}
    if prediction and not prediction_display_allowed(analysis):
        analysis = dict(analysis)
        analysis["prediction"] = None
        analysis["reason"] = (
            "Analiz desteklenmiyor veya gerçek geçmiş veri yeterliliği "
            "tahmin göstermek için yetersiz."
        )
        analysis["warning"] = (
            "LOW, INSUFFICIENT veya veri yok kalitesinde olasılık gösterilmez."
        )
        prediction = {}
    probabilities = (prediction.get("probabilities_percent") or {}).items()
    labels = {"home": "Ev sahibi", "draw": "Beraberlik", "away": "Deplasman", "over25": "2.5 Üst", "btts": "KG Var"}
    probabilities = [(labels.get(key, key), value) for key, value in probabilities]
    message, level = quality_warning(analysis)
    return render_template_string(DETAIL_PAGE, selected=selected.isoformat(), match=match, analysis=analysis, probabilities=probabilities, quality_level=level, quality_message=message)


@app.route("/healthz")
def healthz():
    return {"status": "ok", "service": "avax-v84-beta"}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5085")), debug=False)
