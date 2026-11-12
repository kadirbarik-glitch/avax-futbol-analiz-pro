
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

    # football-data.org fixtures can be analysed directly: the V8 history
    # layer uses the same competition codes and team IDs. Other providers
    # still require the explicit mapping workflow.
    provider = match.get("provider", "")
    league = str(match.get("league_id", "")).upper()
    if provider and provider != "football-data.org":
        return {
            "eligible": False,
            "reason": "Unverified fixture provider",
        }

    if provider == "football-data.org" and league not in {
        "PL", "PD", "SA", "BL1", "FL1", "CL"
    }:
        return {
            "eligible": False,
            "reason": "Competition is not supported by the V8 model",
        }

    return {
        "eligible": True,
        "reason": "Basic safety checks passed",
        "analysis_ready": provider == "football-data.org",
        "requires": [
            "Verified league mapping",
            "Verified team mapping",
            "Historical data sufficiency",
            "Pre-kickoff data integrity",
        ],
    }


def prepare_analysis(match, now=None):
    """Run the existing V8 engine only for same-provider safe fixtures."""

    check = check_analysis_eligibility(match, now)

    result = {
        "match_id": (
            match.get("match_id")
            if isinstance(match, dict)
            else None
        ),
        "eligible": check["eligible"],
        "analysis_ready": False,
        "reason": check["reason"],
        "prediction": None,
        "warning": "No prediction has been generated.",
    }

    if not check["eligible"] or match.get("provider") != "football-data.org":
        return result

    try:
        # Imported lazily to keep page rendering and offline validation light.
        from v8_data import analyze_match

        prediction = analyze_match(
            str(match["league_id"]).upper(),
            int(match["home_team_id"]),
            int(match["away_team_id"]),
            match["kickoff_tr"],
        )
    except (RuntimeError, ValueError, TypeError) as error:
        result["reason"] = "Analysis data unavailable: " + str(error)
        result["warning"] = "No prediction was generated because safety checks failed."
        return result

    result.update({
        "analysis_ready": True,
        "reason": "Prediction generated from football-data.org history",
        "prediction": prediction,
        "warning": (
            "Model output is informational and not calibrated betting advice."
        ),
    })
    return result
