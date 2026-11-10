
"""AVAX V8.4 - Safe daily live fixture verification.

Run manually:
    python v84_daily_live_check.py

Requires API_FOOTBALL_KEY.
No requests occur during import.
"""

import json
import os
import sys
from datetime import datetime

from v84_daily_fixtures import (
    DailyFixtureError,
    get_daily_fixtures,
    today_turkey,
)


def main():
    if not os.environ.get("API_FOOTBALL_KEY", "").strip():
        print("ERROR: API_FOOTBALL_KEY is missing")
        return 1

    selected = today_turkey()

    try:
        result = get_daily_fixtures(selected)
    except (DailyFixtureError, ValueError) as error:
        print("ERROR:", str(error))
        return 1

    matches = result.get("matches", [])

    if not isinstance(matches, list):
        print("ERROR: Invalid match list")
        return 1

    print("AVAX V8.4 DAILY LIVE CHECK")
    print("Date (Turkey):", selected.isoformat())
    print("Total matches:", len(matches))

    countries = set()
    leagues = set()

    for match in matches:
        countries.add(match.get("country", ""))
        leagues.add(
            (
                match.get("country", ""),
                match.get("league", ""),
            )
        )

    print("Countries:", len(countries))
    print("Leagues:", len(leagues))

    print("First 10 matches:")
    for match in matches[:10]:
        print(
            match.get("kickoff_tr", ""),
            "|",
            match.get("country", ""),
            "|",
            match.get("league", ""),
            "|",
            match.get("home_team", ""),
            "-",
            match.get("away_team", ""),
        )

    if not matches:
        print("WARNING: No fixtures returned")
        return 2

    print("LIVE CHECK SUCCESS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
