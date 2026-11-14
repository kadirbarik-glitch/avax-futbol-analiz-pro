"""Chronological V8 calibration research (offline cache only).

This module never downloads fixtures and never changes the live V8 model.
It evaluates only data that was available strictly before each kickoff; equal
kickoff batches are predicted before any result from that batch is recorded.
Run ``python backtest_v84_calibration.py`` after placing validated provider
cache files at ``data_cache/{PL,PD,SA,BL1,FL1,CL}_{2023,2024,2025}.json``.
"""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from backtest_v6 import valid
from v8_live_engine import MARKET_KEYS, predict


LEAGUES = ("PL", "PD", "SA", "BL1", "FL1", "CL")
SEASONS = ("2023", "2024", "2025")
OUTCOME_KEYS = ("home", "draw", "away", "over25", "btts")
GROUPS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}
EPSILON = 1e-12


def ordered_matches(rows):
    """Validate and sort finished fixtures without inventing missing data."""
    rows = valid(rows)
    if len({match["id"] for match in rows}) != len(rows):
        raise ValueError("Duplicate match IDs")
    return sorted(rows, key=lambda match: (match["utcDate"], match["id"]))


def outcome(match):
    score = match["score"]["fullTime"]
    home, away = score["home"], score["away"]
    return {
        "home": int(home > away), "draw": int(home == away),
        "away": int(home < away), "over25": int(home + away >= 3),
        "btts": int(home > 0 and away > 0),
    }


def quality_level(history, match):
    """Use only pre-kickoff team appearance counts for quality grouping."""
    home = len(history[match["homeTeam"]["id"]])
    away = len(history[match["awayTeam"]["id"]])
    count = min(home, away)
    if count < 3:
        return "INSUFFICIENT"
    if count < 5:
        return "LOW"
    if count < 10:
        return "MODERATE"
    return "ADEQUATE"


def baseline_probabilities(history):
    """Smoothed, chronological league-frequency reference model."""
    rows = [outcome(match) for matches in history.values() for match in matches]
    # Every match occurs twice in team histories; deduplicate via ID upstream.
    seen = {}
    for matches in history.values():
        for match in matches:
            seen[match["id"]] = match
    rows = [outcome(match) for match in seen.values()]
    n = len(rows)
    if not n:
        return {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3, "over25": 0.5, "btts": 0.5}
    return {
        "home": (sum(row["home"] for row in rows) + 1) / (n + 3),
        "draw": (sum(row["draw"] for row in rows) + 1) / (n + 3),
        "away": (sum(row["away"] for row in rows) + 1) / (n + 3),
        "over25": (sum(row["over25"] for row in rows) + 1) / (n + 2),
        "btts": (sum(row["btts"] for row in rows) + 1) / (n + 2),
    }


def pre_kickoff_quality_counts(matches):
    """Count quality levels for all fixtures before V8 eligibility filtering."""
    history = defaultdict(list)
    counts = Counter()
    matches = ordered_matches(matches)
    position = 0
    while position < len(matches):
        end = position + 1
        kickoff = matches[position]["utcDate"]
        while end < len(matches) and matches[end]["utcDate"] == kickoff:
            end += 1
        batch = matches[position:end]
        for match in batch:
            counts[quality_level(history, match)] += 1
        for match in batch:
            history[match["homeTeam"]["id"]].append(match)
            history[match["awayTeam"]["id"]].append(match)
        position = end
    return dict(counts)


def chronological_rows(league, matches, predictor=predict):
    """Return V8/reference rows while preventing future-result leakage."""
    matches = ordered_matches(matches)
    history = defaultdict(list)
    rows = []
    position = 0
    while position < len(matches):
        end = position + 1
        kickoff = matches[position]["utcDate"]
        while end < len(matches) and matches[end]["utcDate"] == kickoff:
            end += 1
        batch = matches[position:end]
        # Predict all simultaneous fixtures before adding any of their results.
        reference = baseline_probabilities(history)
        for match in batch:
            level = quality_level(history, match)
            if level == "INSUFFICIENT":
                continue
            prior = [old for matches_for_team in history.values() for old in matches_for_team]
            unique_prior = {old["id"]: old for old in prior}
            try:
                generated = predictor(
                    league, match["homeTeam"]["id"], match["awayTeam"]["id"],
                    kickoff, list(unique_prior.values()),
                )
            except (ValueError, TypeError, KeyError):
                continue
            probabilities = {
                key: generated["probabilities_percent"][key] / 100.0
                for key in OUTCOME_KEYS
            }
            rows.append({"id": match["id"], "kickoff": kickoff, "quality": level,
                         "prediction": probabilities, "baseline": reference, "outcome": outcome(match)})
        for match in batch:
            history[match["homeTeam"]["id"]].append(match)
            history[match["awayTeam"]["id"]].append(match)
        position = end
    return rows


def brier(rows, source, keys):
    if not rows:
        return None
    return sum((row[source][key] - row["outcome"][key]) ** 2 for row in rows for key in keys) / (len(rows) * len(keys))


def log_loss(rows, source, keys):
    if not rows:
        return None
    if len(keys) == 1:
        key = keys[0]
        return -sum(row["outcome"][key] * math.log(max(EPSILON, row[source][key])) + (1 - row["outcome"][key]) * math.log(max(EPSILON, 1 - row[source][key])) for row in rows) / len(rows)
    return -sum(sum(row["outcome"][key] * math.log(max(EPSILON, row[source][key])) for key in keys) for row in rows) / len(rows)


def calibration_table(rows, source, key, bins=10):
    table = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        bucket = [row for row in rows if lower <= row[source][key] < upper or (index == bins - 1 and row[source][key] == 1)]
        if bucket:
            table.append({"range": f"{lower:.1f}-{upper:.1f}", "n": len(bucket),
                          "mean_prediction": round(sum(row[source][key] for row in bucket) / len(bucket), 4),
                          "observed_rate": round(sum(row["outcome"][key] for row in bucket) / len(bucket), 4)})
    return table


def report_rows(rows, all_quality_counts=None):
    report = {"sample_size": len(rows), "quality": Counter(row["quality"] for row in rows), "markets": {}}
    for group, keys in GROUPS.items():
        report["markets"][group] = {
            "v8_brier": brier(rows, "prediction", keys), "baseline_brier": brier(rows, "baseline", keys),
            "v8_log_loss": log_loss(rows, "prediction", keys), "baseline_log_loss": log_loss(rows, "baseline", keys),
            "calibration": {key: calibration_table(rows, "prediction", key) for key in keys},
        }
    report["quality"] = dict(report["quality"])
    report["all_fixture_quality"] = all_quality_counts or report["quality"]
    report["insufficient_excluded"] = report["all_fixture_quality"].get("INSUFFICIENT", 0)
    return report


def load_cached(league, season, cache_dir=Path("data_cache")):
    path = cache_dir / f"{league}_{season}.json"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        payload = payload.get("matches")
    return ordered_matches(payload)


def main():
    for league in LEAGUES:
        for season in SEASONS:
            try:
                matches = load_cached(league, season)
                rows = chronological_rows(league, matches)
                print(json.dumps({"league": league, "season": season, **report_rows(rows, pre_kickoff_quality_counts(matches))}, ensure_ascii=False))
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
                print(json.dumps({"league": league, "season": season, "status": "MISSING_OR_INVALID_DATA", "detail": str(error)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
