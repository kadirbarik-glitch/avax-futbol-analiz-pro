
"""AVAX V8.4 - Daily worldwide football fixtures.

Standalone daily fixture data service.
Does not change existing prediction engines or live deployment.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API_URL = "https://v3.football.api-sports.io"
CACHE_DIR = Path("data_cache") / "daily_v84"
CACHE_MINUTES = 30
MAX_DAYS_AHEAD = 30

TR_TIMEZONE = ZoneInfo("Europe/Istanbul")


class DailyFixtureError(RuntimeError):
    pass


def validate_date(value):
    """Accept a date object or YYYY-MM-DD string."""
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
    """Return selectable dates, starting today."""
    if not isinstance(days, int) or isinstance(days, bool):
        raise ValueError("Invalid day count")

    if not 1 <= days <= MAX_DAYS_AHEAD:
        raise ValueError("Unsupported day count")

    today = today_turkey()
    return [
        (today + timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]


def cache_path(target_date):
    target = validate_date(target_date)
    return CACHE_DIR / ("fixtures_" + target.isoformat() + ".json")


def load_cache(target_date):
    path = cache_path(target_date)

    if not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(payload["fetched_at"])
        if timestamp.tzinfo is None:
            return None

        age = datetime.now(timezone.utc) - timestamp
        if not timedelta(0) <= age < timedelta(minutes=CACHE_MINUTES):
            return None

        if payload.get("date") != validate_date(target_date).isoformat():
            return None

        if not isinstance(payload.get("matches"), list):
            return None

        return payload
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cache(target_date, matches):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(target_date)
    temporary = path.with_suffix(".tmp")

    payload = {
        "date": validate_date(target_date).isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "matches": matches,
    }

    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return payload


def fetch_api_fixtures(target_date, api_key):
    """Fetch fixtures for one UTC date from API-Football."""
    params = urllib.parse.urlencode({
        "date": validate_date(target_date).isoformat(),
        "timezone": "UTC",
    })

    request = urllib.request.Request(
        API_URL + "/fixtures?" + params,
        headers={
            "x-apisports-key": api_key,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise DailyFixtureError(
            "API HTTP status: " + str(error.code)
        ) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise DailyFixtureError("API request failed") from None

    if not isinstance(payload, dict):
        raise DailyFixtureError("Invalid API response")

    if payload.get("errors"):
        raise DailyFixtureError("API reported an error")

    fixtures = payload.get("response")
    if not isinstance(fixtures, list):
        raise DailyFixtureError("Missing fixture list")

    return fixtures


def normalize_daily_fixture(item):
    """Normalize one fixture for daily listing."""
    if not isinstance(item, dict):
        return None

    try:
        fixture = item["fixture"]
        league = item["league"]
        teams = item["teams"]

        fixture_id = fixture["id"]
        kickoff = datetime.fromisoformat(
            fixture["date"].replace("Z", "+00:00")
        )

        if kickoff.tzinfo is None:
            return None

        local_kickoff = kickoff.astimezone(TR_TIMEZONE)

        home = teams["home"]
        away = teams["away"]

        if fixture_id is None:
            return None

        if home.get("id") is None or away.get("id") is None:
            return None

        return {
            "match_id": str(fixture_id),
            "date_tr": local_kickoff.date().isoformat(),
            "kickoff_tr": local_kickoff.isoformat(),
            "league_id": league.get("id"),
            "league": league.get("name", ""),
            "country": league.get("country", ""),
            "home_team_id": str(home["id"]),
            "home_team": home.get("name", ""),
            "away_team_id": str(away["id"]),
            "away_team": away.get("name", ""),
            "status": (fixture.get("status") or {}).get("short", ""),
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def get_daily_fixtures(target_date, force_refresh=False):
    """Get fixtures for a Turkish calendar day.

    Fetches two UTC dates to cover all Turkish local hours.
    """
    selected = validate_date(target_date)
    today = today_turkey()

    if not today <= selected <= today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError("Date outside supported range")

    if not force_refresh:
        cached = load_cache(selected)
        if cached is not None:
            return cached

    api_key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not api_key:
        raise DailyFixtureError("API_FOOTBALL_KEY is not configured")

    matches = {}
    for utc_day in (selected - timedelta(days=1), selected):
        for raw in fetch_api_fixtures(utc_day, api_key):
            match = normalize_daily_fixture(raw)
            if match and match["date_tr"] == selected.isoformat():
                matches[match["match_id"]] = match

    ordered = sorted(
        matches.values(),
        key=lambda match: (
            match["kickoff_tr"],
            match["league"],
            match["match_id"],
        ),
    )

    return save_cache(selected, ordered)


if __name__ == "__main__":
    result = get_daily_fixtures(today_turkey())
    print("Date:", result["date"])
    print("Matches:", len(result["matches"]))
