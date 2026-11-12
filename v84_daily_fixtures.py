"""AVAX V8.4 daily fixtures from the free football-data.org API.

The daily view and prediction history deliberately use the same provider, so
team and competition IDs can be passed to the V8 analysis layer without an
unsafe cross-provider mapping.
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API_URL = "https://api.football-data.org/v4"
CACHE_DIR = Path("data_cache") / "daily_v84"
CACHE_MINUTES = 30
MAX_DAYS_AHEAD = 30
WEEK_DAYS = 7
TR_TIMEZONE = ZoneInfo("Europe/Istanbul")
LOGGER = logging.getLogger(__name__)


class DailyFixtureError(RuntimeError):
    pass


def validate_date(value):
    if isinstance(value, datetime):
        raise ValueError("Expected a date, not datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("Invalid date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Date must be YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise ValueError("Date must be YYYY-MM-DD")
    return parsed


def today_turkey():
    return datetime.now(TR_TIMEZONE).date()


def available_dates(days=7):
    if not isinstance(days, int) or isinstance(days, bool):
        raise ValueError("Invalid day count")
    if not 1 <= days <= MAX_DAYS_AHEAD:
        raise ValueError("Unsupported day count")
    today = today_turkey()
    return [(today + timedelta(days=offset)).isoformat() for offset in range(days)]


def cache_path(target_date):
    return CACHE_DIR / ("fixtures_" + validate_date(target_date).isoformat() + ".json")


def load_cache(target_date):
    path = cache_path(target_date)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(payload["fetched_at"])
        age = datetime.now(timezone.utc) - timestamp
        if timestamp.tzinfo is None or not timedelta(0) <= age < timedelta(minutes=CACHE_MINUTES):
            return None
        if payload.get("date") != validate_date(target_date).isoformat() or not isinstance(payload.get("matches"), list):
            return None
        return payload
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cache(target_date, matches):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(target_date)
    temporary = path.with_suffix(".tmp")
    payload = {"date": validate_date(target_date).isoformat(), "fetched_at": datetime.now(timezone.utc).isoformat(), "matches": matches}
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return payload


def fetch_football_data_fixtures(target_date, api_key):
    """Fetch one UTC date. A free football-data.org token is required."""
    target = validate_date(target_date).isoformat()
    query = urllib.parse.urlencode({"dateFrom": target, "dateTo": target})
    request = urllib.request.Request(API_URL + "/matches?" + query, headers={"X-Auth-Token": api_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise DailyFixtureError("football-data HTTP status: " + str(error.code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise DailyFixtureError("football-data request failed") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise DailyFixtureError("Invalid football-data fixture response")
    return payload["matches"]


def fetch_football_data_fixture_range(start_date, end_date, api_key):
    """Fetch a UTC date range in one request to preserve the free quota."""
    start = validate_date(start_date).isoformat()
    end = validate_date(end_date).isoformat()
    if end < start:
        raise ValueError("End date precedes start date")
    query = urllib.parse.urlencode({"dateFrom": start, "dateTo": end})
    request = urllib.request.Request(
        API_URL + "/matches?" + query,
        headers={"X-Auth-Token": api_key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        LOGGER.warning(
            "football-data weekly request failed http_status=%s date_from=%s date_to=%s",
            error.code, start, end,
        )
        raise DailyFixtureError("football-data HTTP status: " + str(error.code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        LOGGER.warning(
            "football-data weekly request failed date_from=%s date_to=%s",
            start, end,
        )
        raise DailyFixtureError("football-data request failed") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise DailyFixtureError("Invalid football-data fixture response")
    matches = payload["matches"]
    LOGGER.info(
        "football-data weekly response http_status=200 date_from=%s date_to=%s provider_match_count=%s",
        start, end, len(matches),
    )
    return matches


def week_cache_path(start_date):
    return CACHE_DIR / ("week_" + validate_date(start_date).isoformat() + ".json")


def load_week_cache(start_date):
    path = week_cache_path(start_date)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(payload["fetched_at"])
        age = datetime.now(timezone.utc) - timestamp
        if timestamp.tzinfo is None or not timedelta(0) <= age < timedelta(minutes=CACHE_MINUTES):
            return None
        if payload.get("start_date") != validate_date(start_date).isoformat() or not isinstance(payload.get("matches"), list):
            return None
        return payload
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_week_cache(start_date, matches, diagnostics=None):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = week_cache_path(start_date)
    temporary = path.with_suffix(".tmp")
    payload = {
        "start_date": validate_date(start_date).isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "matches": matches,
        "diagnostics": diagnostics or {},
    }
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return payload


def normalize_daily_fixture(item):
    """Normalize one football-data.org match for the Turkish daily calendar."""
    if not isinstance(item, dict):
        return None
    try:
        kickoff = datetime.fromisoformat(str(item["utcDate"]).replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            return None
        home, away = item["homeTeam"], item["awayTeam"]
        competition = item.get("competition") or {}
        match_id = item["id"]
        league_code = str(competition.get("code") or "").strip()
        if match_id is None or home.get("id") is None or away.get("id") is None or not league_code:
            return None
        local_kickoff = kickoff.astimezone(TR_TIMEZONE)
        return {
            "provider": "football-data.org", "match_id": str(match_id),
            "date_tr": local_kickoff.date().isoformat(), "kickoff_tr": local_kickoff.isoformat(),
            "league_id": league_code, "league": str(competition.get("name") or league_code),
            "country": str((competition.get("area") or {}).get("name") or ""),
            "home_team_id": str(home["id"]), "home_team": str(home.get("name") or ""),
            "away_team_id": str(away["id"]), "away_team": str(away.get("name") or ""),
            "status": str(item.get("status") or ""),
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def get_daily_fixtures(target_date, force_refresh=False):
    """Return one Turkish calendar day, safely deduplicated and sorted."""
    selected = validate_date(target_date)
    today = today_turkey()
    if not today <= selected <= today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError("Date outside supported range")
    if not force_refresh:
        cached = load_cache(selected)
        if cached is not None:
            return cached
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not api_key:
        raise DailyFixtureError("FOOTBALL_DATA_API_KEY is not configured")
    matches = {}
    for utc_day in (selected - timedelta(days=1), selected):
        for raw in fetch_football_data_fixtures(utc_day, api_key):
            match = normalize_daily_fixture(raw)
            if match and match["date_tr"] == selected.isoformat():
                matches[match["match_id"]] = match
    ordered = sorted(matches.values(), key=lambda match: (match["kickoff_tr"], match["league"], match["match_id"]))
    return save_cache(selected, ordered)


def get_weekly_fixtures(start_date=None, force_refresh=False):
    """Return seven Turkish calendar days with one API call and cached data."""
    start = validate_date(start_date or today_turkey())
    today = today_turkey()
    end = start + timedelta(days=WEEK_DAYS - 1)
    if not today <= start <= today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError("Date outside supported range")
    if end > today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError("Date outside supported range")
    if not force_refresh:
        cached = load_week_cache(start)
        if cached is not None:
            cached.setdefault("diagnostics", {
                "source": "cache",
                "provider_http_status": "cached",
                "provider_match_count": len(cached["matches"]),
                "filtered_match_count": len(cached["matches"]),
            })
            return cached
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not api_key:
        LOGGER.warning(
            "football-data weekly request skipped missing_api_key date_from=%s date_to=%s",
            start - timedelta(days=1), end,
        )
        raise DailyFixtureError("FOOTBALL_DATA_API_KEY is not configured")
    # Turkey is UTC+3: include the prior UTC day and the last selected UTC day.
    raw_matches = fetch_football_data_fixture_range(
        start - timedelta(days=1), end, api_key
    )
    selected_days = {
        (start + timedelta(days=offset)).isoformat()
        for offset in range(WEEK_DAYS)
    }
    matches = {}
    for raw in raw_matches:
        match = normalize_daily_fixture(raw)
        if match and match["date_tr"] in selected_days:
            matches[match["match_id"]] = match
    ordered = sorted(
        matches.values(),
        key=lambda match: (match["date_tr"], match["kickoff_tr"], match["league"], match["match_id"]),
    )
    diagnostics = {
        "source": "api",
        "provider_http_status": 200,
        "request_date_from": (start - timedelta(days=1)).isoformat(),
        "request_date_to": end.isoformat(),
        "provider_match_count": len(raw_matches),
        "filtered_match_count": len(ordered),
    }
    LOGGER.info(
        "football-data weekly filtered date_from=%s date_to=%s provider_match_count=%s filtered_match_count=%s",
        diagnostics["request_date_from"], diagnostics["request_date_to"],
        diagnostics["provider_match_count"], diagnostics["filtered_match_count"],
    )
    return save_week_cache(start, ordered, diagnostics)
