
"""AVAX V8.2 - Real Champions League data integrity.

Uses cached seasons 2023, 2024 and 2025.
No API requests are made by this script.

Run:
    python test_v82_real_data.py
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
from pathlib import Path
import json
import sys

from backtest_v6 import valid

SEASONS = ("2023", "2024", "2025")
CACHE_DIR = Path("data_cache")
MANIFEST_PATH = CACHE_DIR / "CL_manifest.json"


def parse_date(value):
    date = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if date.tzinfo is None:
        raise ValueError("Timezone missing")

    return date.astimezone(timezone.utc)


def load_manifest(required):
    if not MANIFEST_PATH.exists():
        if required:
            raise RuntimeError(
                f"Missing manifest: {MANIFEST_PATH}"
            )
        return None

    with MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)

    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("competition") != "CL"
        or set(manifest.get("seasons", {})) != set(SEASONS)
    ):
        raise ValueError("Invalid CL cache manifest")

    return manifest


def check_season(season, manifest):
    path = CACHE_DIR / f"CL_{season}.json"

    if not path.exists():
        raise RuntimeError(
            f"Missing cache: {path}"
        )

    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)

    if not isinstance(raw, list):
        raise ValueError("Invalid cache format")

    if manifest:
        entry = manifest["seasons"][season]
        if entry.get("file") != path.name:
            raise ValueError("Manifest file mismatch")
        if entry.get("sha256") != hashlib.sha256(raw_bytes).hexdigest():
            raise ValueError("Cache checksum mismatch")
        if entry.get("raw_matches") != len(raw):
            raise ValueError("Manifest raw match count mismatch")

    matches = valid(raw)

    if not matches:
        raise ValueError("No valid matches")

    if manifest and entry.get("valid_matches") != len(matches):
        raise ValueError("Manifest valid match count mismatch")

    errors = []
    warnings = []
    ids = set()
    dates = []
    kickoff_counts = Counter()

    for match in matches:
        mid = match["id"]

        if mid in ids:
            errors.append(
                f"Duplicate match ID: {mid}"
            )

        ids.add(mid)

        date = parse_date(match["utcDate"])
        dates.append(date)
        kickoff_counts[date] += 1

        home = match["homeTeam"]["id"]
        away = match["awayTeam"]["id"]

        if home == away:
            errors.append(
                f"Same home and away team: {mid}"
            )

        score = match["score"]["fullTime"]

        if (
            score["home"] < 0
            or score["away"] < 0
        ):
            errors.append(
                f"Negative goals: {mid}"
            )

    if dates != sorted(dates):
        errors.append(
            "Matches are not chronological"
        )

    history = Counter()
    eligible = 0
    batches = 0
    simultaneous = 0
    previous_date = None

    pos = 0

    while pos < len(matches):
        date = matches[pos]["utcDate"]
        batch = []

        while (
            pos < len(matches)
            and matches[pos]["utcDate"] == date
        ):
            batch.append(matches[pos])
            pos += 1

        batches += 1

        if len(batch) > 1:
            simultaneous += 1

        if (
            previous_date is not None
            and parse_date(date) < previous_date
        ):
            errors.append(
                "Kickoff chronology violation"
            )

        previous_date = parse_date(date)

        # Read history before updating batch.
        for match in batch:
            home = match["homeTeam"]["id"]
            away = match["awayTeam"]["id"]

            if (
                history[home] >= 3
                and history[away] >= 3
            ):
                eligible += 1

        # Update only after entire batch.
        for match in batch:
            history[match["homeTeam"]["id"]] += 1
            history[match["awayTeam"]["id"]] += 1

    if len(matches) < 50:
        warnings.append(
            "Low number of matches"
        )

    print("\n" + "=" * 50)
    print("AVAX V8.2 REAL DATA TEST")
    print("Season:", season)
    print("Matches:", len(matches))
    print("Unique IDs:", len(ids))
    print("Kickoff groups:", batches)
    print("Simultaneous groups:", simultaneous)
    print("Eligible matches:", eligible)
    print("Warnings:", len(warnings))
    print("Errors:", len(errors))

    for warning in warnings:
        print("WARNING:", warning)

    for error in errors:
        print("ERROR:", error)

    if errors:
        raise AssertionError(
            f"{season}: {len(errors)} errors"
        )

    print("RESULT: PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-manifest",
        action="store_true",
        help="CL cache provenance manifestini zorunlu kilar.",
    )
    args = parser.parse_args()

    failures = []

    try:
        manifest = load_manifest(args.require_manifest)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"MANIFEST: FAIL: {exc}")
        sys.exit(1)

    for season in SEASONS:
        try:
            check_season(season, manifest)
        except (
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            AssertionError,
            OSError,
        ) as exc:
            failures.append(season)
            print(
                f"{season}: FAIL: {exc}"
            )

    if failures:
        print(
            "\nFAILED SEASONS:",
            ", ".join(failures)
        )
        sys.exit(1)

    print(
        "\nALL REAL DATA CHECKS PASSED"
    )


if __name__ == "__main__":
    main()
