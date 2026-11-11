
"""AVAX V8.4 - Safe Analysis Bridge.

Validates daily fixtures before analysis.
Does not call the prediction engine yet.
Does not modify live V8.3.
"""

from datetime import datetime, timezone

from v84_daily_app import (
    classify_match,
    kickoff_is_past,
)


def check_analysis_eligibility(match, now=None):
    """Check whether a match can enter analysis."""

    if now is None:
        now = datetime.now(timezone.utc)

    if not isinstance(match, dict):
        return {
            "eligible": False,
            "reason": "Invalid match data",
        }

    status = match.get("status", "")
    category = classify_match(status)

    if category != "upcoming":
        return {
            "eligible": False,
            "reason": "Match is not upcoming",
        }

    if kickoff_is_past(match, now):
        return {
            "eligible": False,
            "reason": "Kickoff has passed or is invalid",
        }

    required = (
        "match_id",
        "league_id",
        "home_team_id",
        "away_team_id",
        "kickoff_tr",
    )

    for field in required:
        if match.get(field) in (None, ""):
            return {
                "eligible": False,
                "reason": "Missing field: " + field,
            }

    if str(match["home_team_id"]) == str(
        match["away_team_id"]
    ):
        return {
            "eligible": False,
            "reason": "Home and away teams are identical",
        }

    return {
        "eligible": True,
        "reason": "Basic safety checks passed",
        "analysis_ready": False,
        "requires": [
            "Verified league mapping",
            "Verified team mapping",
            "Historical data sufficiency",
            "Pre-kickoff data integrity",
        ],
    }


def prepare_analysis(match, now=None):
    """Prepare a safe result without predictions."""

    check = check_analysis_eligibility(match, now)

    return {
        "match_id": (
            match.get("match_id")
            if isinstance(match, dict)
            else None
        ),
        "eligible": check["eligible"],
        "analysis_ready": False,
        "reason": check["reason"],
        "prediction": None,
        "warning": (
            "V8.4 analysis integration is not active. "
            "No prediction has been generated."
        ),
    }
