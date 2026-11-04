
"""AVAX FUTBOL ANALIZ PRO V8 - Veri Baglantisi.

Gercek lig maclarini mevcut API baglantisindan alir.
Mac baslangicindan sonraki verileri dislar.
"""

from datetime import datetime, timezone

from app_v3 import api_get
from backtest_v6 import valid
from v8_live_engine import predict, parse_date
from v8_models import MODEL_SELECTIONS


def league_history(league, kickoff):
    league = str(league).upper()

    if league not in MODEL_SELECTIONS:
        raise ValueError("Desteklenmeyen lig")

    cutoff = parse_date(kickoff)

    # Avrupa liglerinde sezon genellikle yaz aylarinda baslar.
    season = (
        cutoff.year
        if cutoff.month >= 7
        else cutoff.year - 1
    )

    path = (
        f"/competitions/{league}/matches"
        f"?season={season}&status=FINISHED"
    )

    data, error = api_get(path)

    if error:
        raise RuntimeError(error)

    if not isinstance(data, dict):
        raise RuntimeError("Gecersiz API yaniti")

    matches = data.get("matches")

    if not isinstance(matches, list):
        raise RuntimeError("Mac listesi bulunamadi")

    history = [
        match
        for match in valid(matches)
        if parse_date(match["utcDate"]) < cutoff
        and match.get("status") == "FINISHED"
    ]

    return history


def analyze_match(
    league,
    home_id,
    away_id,
    kickoff,
):
    """Gercek lig verileriyle V8 tahmini uret."""

    kickoff_time = parse_date(kickoff)

    if kickoff_time <= datetime.now(timezone.utc):
        raise ValueError(
            "Yalnizca baslamamis maclar analiz edilir"
        )

    history = league_history(league, kickoff)

    if len(history) < 20:
        raise ValueError(
            "Bu sezon yeterli lig verisi bulunamadi"
        )

    result = predict(
        league,
        int(home_id),
        int(away_id),
        kickoff,
        history,
    )

    result["data_source"] = "football-data.org"
    result["historical_matches_loaded"] = len(history)
    result["live_odds_included"] = False

    return result
