
"""AVAX V8.4 - Safe Team and League Mapping.

Maps API-Football IDs to football-data.org IDs.
Only explicitly verified mappings are accepted.

Development module. No API calls or live deployment.
"""

from dataclasses import dataclass
from typing import Optional


class MappingError(ValueError):
    """Raised when an ID mapping is unsafe or missing."""


@dataclass(frozen=True)
class LeagueMapping:
    api_football_id: int
    football_data_code: str
    verified: bool = False


@dataclass(frozen=True)
class TeamMapping:
    api_football_id: int
    football_data_id: int
    league_code: str
    verified: bool = False


SUPPORTED_LEAGUES = frozenset({
    "PL", "PD", "SA", "BL1", "FL1", "CL"
})


# Add entries only after verifying both providers.
# Never assume identical numeric IDs mean identical teams.
LEAGUE_MAPPINGS = {}

TEAM_MAPPINGS = {}


def normalize_id(value):
    """Convert a positive integer ID safely."""

    if isinstance(value, bool):
        raise MappingError("Boolean ID is invalid")

    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        raise MappingError("Invalid ID") from None

    if normalized <= 0:
        raise MappingError("ID must be positive")

    if isinstance(value, float):
        raise MappingError("Float ID is not allowed")

    if isinstance(value, str):
        if not value.isdecimal():
            raise MappingError("Invalid ID format")

    return normalized


def resolve_league(api_league_id):
    """Resolve an explicitly verified league."""

    league_id = normalize_id(api_league_id)
    mapping = LEAGUE_MAPPINGS.get(league_id)

    if mapping is None:
        raise MappingError("League mapping not found")

    if not isinstance(mapping, LeagueMapping):
        raise MappingError("Invalid league mapping")

    if not mapping.verified:
        raise MappingError("League mapping not verified")

    if mapping.football_data_code not in SUPPORTED_LEAGUES:
        raise MappingError("Unsupported target league")

    if mapping.api_football_id != league_id:
        raise MappingError("League ID mismatch")

    return mapping.football_data_code


def resolve_team(api_team_id, league_code):
    """Resolve an explicitly verified team."""

    team_id = normalize_id(api_team_id)

    if league_code not in SUPPORTED_LEAGUES:
        raise MappingError("Unsupported league")

    mapping = TEAM_MAPPINGS.get(
        (league_code, team_id)
    )

    if mapping is None:
        raise MappingError("Team mapping not found")

    if not isinstance(mapping, TeamMapping):
        raise MappingError("Invalid team mapping")

    if not mapping.verified:
        raise MappingError("Team mapping not verified")

    if mapping.league_code != league_code:
        raise MappingError("Team league mismatch")

    if mapping.api_football_id != team_id:
        raise MappingError("Team ID mismatch")

    return normalize_id(mapping.football_data_id)


def resolve_match(match):
    """Resolve league and both teams safely.

    Reject unknown, unverified or conflicting mappings.
    """

    if not isinstance(match, dict):
        raise MappingError("Invalid match")

    league_code = resolve_league(
        match.get("league_id")
    )

    home_id = resolve_team(
        match.get("home_team_id"),
        league_code,
    )

    away_id = resolve_team(
        match.get("away_team_id"),
        league_code,
    )

    if home_id == away_id:
        raise MappingError(
            "Home and away teams cannot be identical"
        )

    return {
        "league": league_code,
        "home_id": home_id,
        "away_id": away_id,
        "verified": True,
    }


def mapping_status(match):
    """Return a safe status without raising errors."""

    try:
        resolved = resolve_match(match)

        return {
            "ready": True,
            "mapping": resolved,
            "reason": "Verified mappings available",
        }

    except MappingError as error:
        return {
            "ready": False,
            "mapping": None,
            "reason": str(error),
        }
