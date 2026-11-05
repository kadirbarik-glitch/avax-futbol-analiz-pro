"""AVAX FUTBOL ANALIZ PRO V8.3 - Data Layer.

Historical competition and team freshness.
Team history sufficiency and market-level warnings.
Only finished pre-kickoff matches are used.

Quality indicators are heuristic, not calibrated
prediction confidence or validated accuracy.
"""

from datetime import datetime, timezone

from app_v3 import api_get
from backtest_v6 import valid
from v8_live_engine import predict, parse_date
from v8_models import MODEL_SELECTIONS


QUALITY_ORDER = {
    "INSUFFICIENT": 0,
    "LOW": 1,
    "MODERATE": 2,
    "ADEQUATE": 3,
}

FRESHNESS_ORDER = {
    "NO_DATA": 0,
    "STALE": 1,
    "AGING": 2,
    "FRESH": 3,
}

MARKET_NAMES = {
    "match_result": "Mac sonucu",
    "over_under": "2.5 Alt/Ust",
    "btts": "KG Var/Yok",
}


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


def history_sufficiency(count):
    """Heuristic warning, not calibrated confidence."""

    if count < 3:
        return {
            "level": "INSUFFICIENT",
            "message": (
                "Tahmin icin yeterli takim "
                "gecmisi bulunmuyor."
            ),
        }

    if count < 5:
        return {
            "level": "LOW",
            "message": (
                "Takimin gecmis mac sayisi az. "
                "Tahmin belirsizligi yuksek olabilir."
            ),
        }

    if count < 10:
        return {
            "level": "MODERATE",
            "message": (
                "Orta duzeyde takim gecmisi var. "
                "Tahmin dikkatli yorumlanmali."
            ),
        }

    return {
        "level": "ADEQUATE",
        "message": (
            "Daha fazla takim gecmisi mevcut. "
            "Bu, tahmin dogrulugunu garanti etmez."
        ),
    }


def team_freshness(history, team_id, kickoff):
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

    count = len(team_matches)
    sufficiency = history_sufficiency(count)

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
            "sufficiency_level": sufficiency["level"],
            "sufficiency_message": sufficiency["message"],
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
        "matches": count,
        "latest_match_utc": latest.isoformat(),
        "days_since_latest": round(days, 1),
        "freshness_status": status,
        "freshness_message": message,
        "sufficiency_level": sufficiency["level"],
        "sufficiency_message": sufficiency["message"],
    }


def market_data_quality(home_info, away_info):
    """Conservative shared-input quality assessment.

    All three markets use the same team-history inputs.
    Market-specific accuracy requires separate backtests.
    """

    levels = [
        home_info["sufficiency_level"],
        away_info["sufficiency_level"],
    ]

    freshness_levels = [
        home_info["freshness_status"],
        away_info["freshness_status"],
    ]

    weakest_level = min(
        levels,
        key=lambda x: QUALITY_ORDER.get(x, 0),
    )

    weakest_freshness = min(
        freshness_levels,
        key=lambda x: FRESHNESS_ORDER.get(x, 0),
    )

    if weakest_freshness == "NO_DATA":
        effective_level = "INSUFFICIENT"
    elif weakest_freshness == "STALE":
        effective_level = min(
            weakest_level,
            "LOW",
            key=lambda x: QUALITY_ORDER[x],
        )
    else:
        effective_level = weakest_level

    if effective_level == "INSUFFICIENT":
        message = (
            "Takim gecmisi yetersiz veya eksik. "
            "Bu tahminin guvenilirligi belirsiz."
        )
    elif effective_level == "LOW":
        message = (
            "Az veya eski takim verisi kullaniliyor. "
            "Yuksek olasiliklar dikkatle yorumlanmali."
        )
    elif effective_level == "MODERATE":
        message = (
            "Orta duzey veri mevcut. "
            "Tahmin dogrulugu garanti edilmez."
        )
    else:
        message = (
            "Daha kapsamli takim gecmisi mevcut. "
            "Modelin isabeti ayrica dogrulanmalidir."
        )

    output = {}

    for key, name in MARKET_NAMES.items():
        output[key] = {
            "name": name,
            "level": effective_level,
            "freshness": weakest_freshness,
            "home_matches": home_info["matches"],
            "away_matches": away_info["matches"],
            "message": message,
            "independently_validated": False,
        }

    return output


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

    home_info = team_freshness(
        history, home_id, kickoff
    )

    away_info = team_freshness(
        history, away_id, kickoff
    )

    result["home_team_freshness"] = home_info
    result["away_team_freshness"] = away_info

    levels = (
        home_info["sufficiency_level"],
        away_info["sufficiency_level"],
    )

    if "INSUFFICIENT" in levels:
        result["data_quality_warning"] = (
            "En az bir takim icin gecmis "
            "mac sayisi yetersiz."
        )
    elif "LOW" in levels:
        result["data_quality_warning"] = (
            "En az bir takim icin gecmis "
            "mac sayisi az. Tahminlerin "
            "belirsizligi yuksek olabilir."
        )
    elif "MODERATE" in levels:
        result["data_quality_warning"] = (
            "Takim gecmisleri orta duzeyde. "
            "Tahminleri dikkatli yorumlayin."
        )
    else:
        result["data_quality_warning"] = (
            "Takim gecmisleri daha kapsamli. "
            "Bu, tahminin dogru olacagi "
            "anlamina gelmez."
        )

    result["market_data_quality"] = (
        market_data_quality(
            home_info,
            away_info,
        )
    )

    return result
