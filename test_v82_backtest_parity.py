"""AVAX V8.2 - Strict backtest/live parity.

Match-ID based reference mapping.
No silent skipping of eligible matches.
Uses cached Champions League data.

Run:
python -m unittest -v test_v82_backtest_parity
"""

import unittest
from collections import Counter

from backtest_v6 import evaluate as evaluate_v6
from backtest_v7 import CONFIGS, evaluate_v7
from backtest_v82_models import load_matches
from v8_live_engine import predict
from v8_models import get_league_models


SEASONS = ("2023", "2024", "2025")

MARKET_KEYS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}

TOLERANCE = 0.000051


def eligible_matches(matches):
    """Identify eligible matches before each kickoff."""

    history = Counter()
    eligible = []
    pos = 0

    while pos < len(matches):
        end = pos + 1
        kickoff = matches[pos]["utcDate"]

        while (
            end < len(matches)
            and matches[end]["utcDate"] == kickoff
        ):
            end += 1

        batch = matches[pos:end]

        # Evaluate the entire batch before updates.
        for match in batch:
            hid = match["homeTeam"]["id"]
            aid = match["awayTeam"]["id"]

            if history[hid] >= 3 and history[aid] >= 3:
                eligible.append(match)

        for match in batch:
            history[match["homeTeam"]["id"]] += 1
            history[match["awayTeam"]["id"]] += 1

        pos = end

    return eligible


def reference_rows(matches, model):
    if model.startswith("V6_"):
        blend = float(model.split("_", 1)[1])
        return evaluate_v6(matches, blend)

    if model.startswith("V7_"):
        index = int(model.split("_", 1)[1])

        if not 0 <= index < len(CONFIGS):
            raise AssertionError("Invalid V7 index")

        return evaluate_v7(matches, CONFIGS[index])

    raise AssertionError("Unknown model: " + model)


def reference_by_match_id(matches, model, eligible):
    """Map ordered backtest rows to eligible match IDs.

    Both V6 and V7 append one prediction for each
    eligible match in chronological batch order.
    Assert coverage before creating the mapping.
    """

    rows = reference_rows(matches, model)

    if len(rows) != len(eligible):
        raise AssertionError(
            f"{model}: reference coverage mismatch: "
            f"rows={len(rows)}, eligible={len(eligible)}"
        )

    mapping = {}

    for match, (probability, outcome) in zip(
        eligible, rows
    ):
        mid = match["id"]

        if mid in mapping:
            raise AssertionError(
                f"Duplicate reference match ID: {mid}"
            )

        mapping[mid] = probability

        score = match["score"]["fullTime"]
        hg, ag = score["home"], score["away"]

        expected_outcome = {
            "home": int(hg > ag),
            "draw": int(hg == ag),
            "away": int(hg < ag),
            "over25": int(hg + ag >= 3),
            "btts": int(hg > 0 and ag > 0),
        }

        if outcome != expected_outcome:
            raise AssertionError(
                f"{model}: outcome alignment "
                f"failed for match {mid}"
            )

    return mapping


def compare_season(season):
    matches = load_matches(season)

    if len({m["id"] for m in matches}) != len(matches):
        raise AssertionError("Duplicate match IDs")

    if matches != sorted(
        matches,
        key=lambda m: (m["utcDate"], m["id"])
    ):
        raise AssertionError("Matches not sorted")

    eligible = eligible_matches(matches)
    selected = get_league_models("CL")

    if set(selected) != set(MARKET_KEYS):
        raise AssertionError("Market selection mismatch")

    references = {
        model: reference_by_match_id(
            matches, model, eligible
        )
        for model in set(selected.values())
    }

    compared_matches = 0
    compared_values = 0
    missing = []
    mismatches = []

    for match in eligible:
        mid = match["id"]
        kickoff = match["utcDate"]

        # The current match and all later results
        # must be unavailable to the live engine.
        earlier = [
            m for m in matches
            if m["utcDate"] < kickoff
        ]

        try:
            live = predict(
                "CL",
                match["homeTeam"]["id"],
                match["awayTeam"]["id"],
                kickoff,
                earlier,
            )
        except (ValueError, TypeError, KeyError) as exc:
            missing.append((mid, str(exc)))
            continue

        compared_matches += 1

        for market, model in selected.items():
            reference = references[model].get(mid)

            if reference is None:
                missing.append(
                    (mid, f"Missing {model} reference")
                )
                continue

            live_model = live["models"][market]["model"]

            if live_model != model:
                mismatches.append(
                    (mid, market, "wrong model")
                )
                continue

            for key in MARKET_KEYS[market]:
                actual = (
                    live["probabilities_percent"][key]
                    / 100.0
                )
                expected = reference[key]

                compared_values += 1

                if abs(actual - expected) > TOLERANCE:
                    mismatches.append(
                        (
                            mid,
                            market,
                            key,
                            round(actual, 7),
                            round(expected, 7),
                        )
                    )

    expected_values = sum(
        len(keys) for keys in MARKET_KEYS.values()
    ) * len(eligible)

    print(f"\nSEASON: {season}")
    print(f"Total matches: {len(matches)}")
    print(f"Eligible matches: {len(eligible)}")
    print(f"Compared matches: {compared_matches}")
    print(f"Compared probabilities: {compared_values}")
    print(f"Expected probabilities: {expected_values}")
    print(f"Missing: {len(missing)}")
    print(f"Mismatches: {len(mismatches)}")

    for item in missing[:10]:
        print("MISSING:", item)

    for item in mismatches[:10]:
        print("MISMATCH:", item)

    if missing or mismatches:
        raise AssertionError(
            f"{season}: parity check failed"
        )

    if compared_matches != len(eligible):
        raise AssertionError(
            "Incomplete match coverage"
        )

    if compared_values != expected_values:
        raise AssertionError(
            "Incomplete probability coverage"
        )

    if len(eligible) < 20:
        raise AssertionError(
            "Insufficient eligible matches"
        )

    print("RESULT: STRICT PARITY PASS")


class StrictParityTests(unittest.TestCase):

    def test_2023(self):
        compare_season("2023")

    def test_2024(self):
        compare_season("2024")

    def test_2025(self):
        compare_season("2025")


if __name__ == "__main__":
    unittest.main(verbosity=2)
