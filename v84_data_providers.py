"""AVAX V8.4 - Multi-provider football data foundation.

This module does not make network requests or alter existing predictions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


class ProviderDataError(ValueError):
    """Raised when provider data is missing or invalid."""


@dataclass(frozen=True)
class MatchRecord:
    provider: str
    competition: str
    match_id: str
    kickoff_utc: str
    home_team_id: str
    away_team_id: str
    status: str
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "competition": self.competition,
            "match_id": self.match_id,
            "kickoff_utc": self.kickoff_utc,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "status": self.status,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
        }


def required(value: Any, field: str) -> str:
    if value is None or isinstance(value, bool):
        raise ProviderDataError("Missing field: " + field)
    result = str(value).strip()
    if not result:
        raise ProviderDataError("Missing field: " + field)
    return result


def normalize_football_data(
    match: Dict[str, Any], competition: str
) -> MatchRecord:
    """Normalize a football-data.org v4 match."""
    if not isinstance(match, dict):
        raise ProviderDataError("Match must be an object")

    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    score = (match.get("score") or {}).get("fullTime") or {}

    return MatchRecord(
        provider="football-data.org",
        competition=required(competition, "competition"),
        match_id=required(match.get("id"), "match.id"),
        kickoff_utc=required(match.get("utcDate"), "utcDate"),
        home_team_id=required(home.get("id"), "homeTeam.id"),
        away_team_id=required(away.get("id"), "awayTeam.id"),
        status=required(match.get("status"), "status"),
        home_goals=score.get("home"),
        away_goals=score.get("away"),
    )


def normalize_api_football(
    match: Dict[str, Any], competition: str
) -> MatchRecord:
    """Normalize an API-Football fixture response."""
    if not isinstance(match, dict):
        raise ProviderDataError("Match must be an object")

    fixture = match.get("fixture") or {}
    teams = match.get("teams") or {}
    goals = match.get("goals") or {}
    status = fixture.get("status") or {}

    return MatchRecord(
        provider="api-football",
        competition=required(competition, "competition"),
        match_id=required(fixture.get("id"), "fixture.id"),
        kickoff_utc=required(fixture.get("date"), "fixture.date"),
        home_team_id=required(
            (teams.get("home") or {}).get("id"), "teams.home.id"
        ),
        away_team_id=required(
            (teams.get("away") or {}).get("id"), "teams.away.id"
        ),
        status=required(status.get("short"), "fixture.status.short"),
        home_goals=goals.get("home"),
        away_goals=goals.get("away"),
    )
