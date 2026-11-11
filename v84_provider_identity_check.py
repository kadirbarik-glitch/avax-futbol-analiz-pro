
"""AVAX V8.4 - Provider Identity Check.

Read-only Premier League team identity comparison.
Never automatically verifies or activates mappings.
Does not modify existing mapping tables or live V8.3.
"""

import json
import os
import urllib.error
import urllib.request

from v84_mapping_verifier import (
    TeamIdentity,
    find_candidates,
    verification_report,
)

API_FOOTBALL_URL = (
    "https://v3.football.api-sports.io"
    "/teams?league=39&season={season}"
)

FOOTBALL_DATA_URL = (
    "https://api.football-data.org/v4"
    "/competitions/PL/teams"
)

SAFE_API_ERRORS = {
    "token_missing": "API key is missing or invalid",
    "token_invalid": "API key is missing or invalid",
    "token_expired": "API key has expired",
    "token_limit": "API request limit reached",
    "rateLimit": "API rate limit reached",
    "requests": "API request quota or limit error",
    "access": "API access denied",
    "plan": "API subscription or plan restriction",
}


class ProviderIdentityError(RuntimeError):
    """Provider request or response error."""


def fetch_json(url, headers):
    """Fetch JSON from an approved provider."""

    request = urllib.request.Request(
        url,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(
            request, timeout=25
        ) as response:
            return json.load(response)

    except urllib.error.HTTPError as error:
        raise ProviderIdentityError(
            f"Provider HTTP error: {error.code}"
        ) from None

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
    ):
        raise ProviderIdentityError(
            "Provider request failed"
        ) from None


def safe_error_summary(errors):
    """Summarize API errors without logging secrets."""

    if not errors:
        return "No API error details provided"

    if isinstance(errors, dict):
        messages = []
        for key in errors:
            messages.append(
                SAFE_API_ERRORS.get(
                    key,
                    f"API error category: {key}"
                    if key in (
                        "token_missing",
                        "token_invalid",
                        "token_expired",
                        "token_limit",
                        "rateLimit",
                        "requests",
                        "access",
                        "plan",
                    )
                    else "Unrecognized API error category",
                )
            )
        return "; ".join(messages)

    if isinstance(errors, list):
        return (
            "API returned an error list "
            f"with {len(errors)} item(s)"
        )

    return "API returned an unexpected error format"


def fetch_api_football_teams(season):
    """Read Premier League teams from API-Football."""

    api_key = os.environ.get(
        "API_FOOTBALL_KEY", ""
    ).strip()

    if not api_key:
        raise ProviderIdentityError(
            "API_FOOTBALL_KEY is missing"
        )

    if (
        not isinstance(season, int)
        or isinstance(season, bool)
        or not 2020 <= season <= 2100
    ):
        raise ProviderIdentityError(
            "Invalid season"
        )

    payload = fetch_json(
        API_FOOTBALL_URL.format(season=season),
        {
            "x-apisports-key": api_key,
            "Accept": "application/json",
        },
    )

    if not isinstance(payload, dict):
        raise ProviderIdentityError(
            "Invalid API-Football response: "
            "expected JSON object"
        )

    errors = payload.get("errors")

    if errors:
        raise ProviderIdentityError(
            "API-Football error: "
            + safe_error_summary(errors)
        )

    if not isinstance(
        payload.get("response"), list
    ):
        raise ProviderIdentityError(
            "Invalid API-Football response: "
            "response is not a list"
        )

    teams = []

    for item in payload["response"]:
        try:
            team = item["team"]

            teams.append(
                TeamIdentity(
                    provider="api-football",
                    team_id=int(team["id"]),
                    name=team["name"],
                    country="England",
                    league="Premier League",
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

    return teams


def fetch_football_data_teams():
    """Read Premier League teams from football-data."""

    api_key = os.environ.get(
        "FOOTBALL_DATA_API_KEY", ""
    ).strip()

    if not api_key:
        raise ProviderIdentityError(
            "FOOTBALL_DATA_API_KEY is missing"
        )

    payload = fetch_json(
        FOOTBALL_DATA_URL,
        {
            "X-Auth-Token": api_key,
            "Accept": "application/json",
        },
    )

    if (
        not isinstance(payload, dict)
        or not isinstance(
            payload.get("teams"), list
        )
    ):
        raise ProviderIdentityError(
            "Invalid football-data response"
        )

    teams = []

    for team in payload["teams"]:
        try:
            teams.append(
                TeamIdentity(
                    provider="football-data",
                    team_id=int(team["id"]),
                    name=team["name"],
                    country="England",
                    league="Premier League",
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

    return teams


def build_identity_report(
    season,
    minimum_similarity=0.60,
):
    """Build a pending-only comparison report."""

    sources = fetch_api_football_teams(
        season
    )

    targets = fetch_football_data_teams()

    results = []

    for source in sources:
        candidates = find_candidates(
            source,
            targets,
            minimum_similarity=minimum_similarity,
        )

        results.append({
            "source_id": source.team_id,
            "source_name": source.name,
            "candidates": [
                verification_report(candidate)
                for candidate in candidates
            ],
        })

    return {
        "season": season,
        "source_count": len(sources),
        "target_count": len(targets),
        "results": results,
        "verified_mappings": 0,
        "auto_activated": False,
        "warning": (
            "Candidates require manual identity "
            "verification before activation."
        ),
    }


if __name__ == "__main__":
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(
        ZoneInfo("Europe/Istanbul")
    )

    season = (
        today.year
        if today.month >= 7
        else today.year - 1
    )

    try:
        report = build_identity_report(season)

        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )

    except ProviderIdentityError as error:
        print("Identity check failed:", error)
        raise SystemExit(1)
