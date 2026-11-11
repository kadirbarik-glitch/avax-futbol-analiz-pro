
"""AVAX V8.4 - Free Team Catalog.

Read-only team catalog using football-data.org.
No automatic provider mappings or live deployment.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://api.football-data.org/v4"

SUPPORTED_LEAGUES = (
    "PL",
    "PD",
    "SA",
    "BL1",
    "FL1",
    "CL",
)


class TeamCatalogError(RuntimeError):
    """Safe team catalog error."""


def fetch_json(path):
    """Read JSON without exposing the API token."""

    token = os.environ.get(
        "FOOTBALL_DATA_API_KEY", ""
    ).strip()

    if not token:
        raise TeamCatalogError(
            "FOOTBALL_DATA_API_KEY is missing"
        )

    request = urllib.request.Request(
        API_BASE + path,
        headers={
            "X-Auth-Token": token,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=25
        ) as response:
            return json.load(response)

    except urllib.error.HTTPError as error:
        raise TeamCatalogError(
            f"football-data HTTP error: {error.code}"
        ) from None

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
    ):
        raise TeamCatalogError(
            "football-data request failed"
        ) from None


def normalize_team(team, league):
    """Validate one team record."""

    if not isinstance(team, dict):
        return None

    try:
        team_id = int(team["id"])
        name = str(team["name"]).strip()
    except (KeyError, TypeError, ValueError):
        return None

    if team_id <= 0 or not name:
        return None

    return {
        "provider": "football-data",
        "team_id": team_id,
        "name": name,
        "short_name": str(
            team.get("shortName") or ""
        ).strip(),
        "tla": str(
            team.get("tla") or ""
        ).strip(),
        "league": league,
        "country": str(
            (team.get("area") or {}).get("name")
            or ""
        ).strip(),
    }


def build_team_catalog(league="PL"):
    """Build a read-only, unverified team catalog."""

    if league not in SUPPORTED_LEAGUES:
        raise TeamCatalogError(
            "Unsupported league"
        )

    payload = fetch_json(
        f"/competitions/{league}/teams"
    )

    if (
        not isinstance(payload, dict)
        or not isinstance(
            payload.get("teams"), list
        )
    ):
        raise TeamCatalogError(
            "Invalid football-data team response"
        )

    teams = []
    seen_ids = set()

    for raw_team in payload["teams"]:
        team = normalize_team(
            raw_team, league
        )

        if team is None:
            continue

        if team["team_id"] in seen_ids:
            continue

        seen_ids.add(team["team_id"])
        teams.append(team)

    if not teams:
        raise TeamCatalogError(
            "No valid teams returned"
        )

    teams.sort(
        key=lambda item: (
            item["name"].casefold(),
            item["team_id"],
        )
    )

    return {
        "provider": "football-data",
        "league": league,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "team_count": len(teams),
        "teams": teams,
        "verified_mappings": 0,
        "auto_activated": False,
        "warning": (
            "This is a provider team catalog, "
            "not a verified cross-provider mapping."
        ),
    }


if __name__ == "__main__":
    try:
        report = build_team_catalog("PL")

        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )

    except TeamCatalogError as error:
        print(
            "Team catalog failed:", error
        )
        raise SystemExit(1)
