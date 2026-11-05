"""AVAX FUTBOL ANALIZ PRO V8.2 - Data Layer.

Competition and team-specific historical freshness.
Only finished matches before kickoff are used.
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


def freshness_status(days):
    """Classify age of latest historical match."""

    if days is None:
        return (
            "NO_DATA",
            "Gecmis mac verisi bulunamadi.",
        )

    if days <= 14:
        return (
            "FRESH",
            "Gecmis veriler yakin tarihli.",
        )

    if days <= 35:
        return (
            "AGING",
            "Gecmis veriler bir miktar eski.",
        )

    return (
        "STALE",
        "Gecmis veriler eski olabilir.",
    )


def freshness_info(history, kickoff):
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

    days = (
        cutoff - latest
    ).total_seconds() / 86400

    if days < 0:
        raise ValueError(
            "Gelecek mac verisi tespit edildi"
        )

    status, message = freshness_status(days)

    return {
        "latest_match_utc": latest.isoformat(),
        "days_since_latest": round(days, 1),
        "freshness_status": status,
        "freshness_message": message,
    }


def team_freshness(history, team_id, kickoff):
    """Calculate freshness for a specific team."""

    cutoff = parse_date(kickoff)
    team_id = int(team_id)

    team_matches = [
        match
        for match in history
        if (
            match["homeTeam"]["id"] == team_id
            or match["awayTeam"]["id"] == team_id
        )
        and parse_date(match["utcDate"]) < cutoff
    ]

    team_matches.sort(
        key=lambda m: (
            parse_date(m["utcDate"]),
            m["id"],
        )
    )

    if not team_matches:
        return {
            "team_id": team_id,
            "matches": 0,
            "latest_match_utc": None,
            "days_since_latest": None,
            "freshness_status": "NO_DATA",
            "freshness_message": (
                "Bu takim icin gecmis mac yok."
            ),
        }

    latest = parse_date(
        team_matches[-1]["utcDate"]
    )

    days = (
        cutoff - latest
    ).total_seconds() / 86400

    if days < 0:
        raise ValueError(
            "Gelecek takim verisi tespit edildi"
        )

    status, message = freshness_status(days)

    return {
        "team_id": team_id,
        "matches": len(team_matches),
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

    result["home_team_freshness"] = team_freshness(
        history, home_id, kickoff
    )

    result["away_team_freshness"] = team_freshness(
        history, away_id, kickoff
    )

    return result
