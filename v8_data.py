"""AVAX FUTBOL ANALIZ PRO V8.2 - Data Layer.

Fetches historical competition results.
Reports latest match and data freshness.

Experimental predictions. No guarantees.
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


def freshness_info(history, kickoff):
    """Describe historical data age at prediction time."""

    if not history:
        return {
            "latest_match_utc": None,
            "days_since_latest": None,
            "freshness_status": "NO_DATA",
            "freshness_message": (
                "Gecmis mac verisi bulunamadi."
            ),
        }

    cutoff = parse_date(kickoff)

    latest = max(
        parse_date(m["utcDate"])
        for m in history
    )

    days = (cutoff - latest).total_seconds() / 86400

    if days < 0:
        raise ValueError(
            "Gelecek mac verisi tespit edildi"
        )

    if days <= 14:
        status = "FRESH"
        message = "Gecmis veriler yakin tarihli."
    elif days <= 35:
        status = "AGING"
        message = "Gecmis veriler bir miktar eski."
    else:
        status = "STALE"
        message = (
            "Gecmis veriler eski olabilir. "
            "Tahmini dikkatli degerlendirin."
        )

    return {
        "latest_match_utc": latest.isoformat(),
        "days_since_latest": round(days, 1),
        "freshness_status": status,
        "freshness_message": message,
    }


def analyze_match(
    league,
    home_id,
    away_id,
    kickoff,
):
    """Generate prediction and data freshness report."""

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

    result.update(
        freshness_info(history, kickoff)
    )

    return result
