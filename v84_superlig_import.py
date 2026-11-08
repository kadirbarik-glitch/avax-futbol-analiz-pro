"""AVAX V8.4 - Super Lig historical data importer.

Run manually in a trusted environment:
    python v84_superlig_import.py

Requires:
    API_FOOTBALL_KEY environment variable.

No network requests occur when this module is imported.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from v84_data_providers import (
    ProviderDataError,
    normalize_api_football,
)

API_URL = "https://v3.football.api-sports.io"
LEAGUE_ID = 203
SEASONS = (2022, 2023, 2024)
OUTPUT_DIR = Path("data_cache") / "superlig_v84"


def fetch_fixtures(season, api_key):
    """Fetch one season without printing the secret."""
    if season not in SEASONS:
        raise ValueError("Unsupported season")

    params = urllib.parse.urlencode({
        "league": LEAGUE_ID,
        "season": season,
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
        raise RuntimeError(
            "API HTTP status: " + str(error.code)
        ) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise RuntimeError("API request failed") from None

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid API response")

    errors = payload.get("errors")
    if errors:
        raise RuntimeError("API reported an access or data error")

    fixtures = payload.get("response")
    if not isinstance(fixtures, list):
        raise RuntimeError("Missing fixture list")

    return fixtures


def normalize_season(fixtures):
    """Keep finished matches with valid scores."""
    records = []
    seen = set()

    for fixture in fixtures:
        try:
            match = normalize_api_football(fixture, "TR")
        except (ProviderDataError, AttributeError, TypeError):
            continue

        if match.status not in ("FT", "AET", "PEN"):
            continue

        if (
            not isinstance(match.home_goals, int)
            or isinstance(match.home_goals, bool)
            or not isinstance(match.away_goals, int)
            or isinstance(match.away_goals, bool)
            or match.home_goals < 0
            or match.away_goals < 0
        ):
            continue

        if match.match_id in seen:
            continue

        seen.add(match.match_id)
        records.append(match.as_dict())

    records.sort(
        key=lambda item: (
            item["kickoff_utc"],
            item["match_id"],
        )
    )
    return records


def import_season(season, api_key, output_dir=OUTPUT_DIR):
    fixtures = fetch_fixtures(season, api_key)
    records = normalize_season(fixtures)

    if not records:
        raise RuntimeError("No valid finished matches")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / ("superlig_" + str(season) + ".json")
    temporary = destination.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(
            {
                "provider": "api-football",
                "league_id": LEAGUE_ID,
                "season": season,
                "matches": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(destination)

    print("Season:", season, "finished matches:", len(records))
    return destination


def main():
    api_key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not api_key:
        raise SystemExit("API_FOOTBALL_KEY is not configured")

    for index, season in enumerate(SEASONS):
        import_season(season, api_key)
        if index < len(SEASONS) - 1:
            time.sleep(2)

    print("Historical import completed")


if __name__ == "__main__":
    main()
