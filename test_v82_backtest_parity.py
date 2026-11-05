
"""AVAX V8.2 - Backtest / live engine parity.

Compares live engine probabilities against
historical V6/V7 evaluation probabilities.

Uses cached Champions League data.
No API requests or betting actions.
"""

import unittest

from backtest_v6 import (
    valid,
    evaluate as evaluate_v6,
)
from backtest_v7 import (
    CONFIGS,
    evaluate_v7,
)
from backtest_v82_models import load_matches
from v8_live_engine import predict
from v8_models import get_league_models


SEASONS = ("2023", "2024", "2025")
MARKET_KEYS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}


def get_reference_predictions(matches, model):
    """Produce reference probabilities by kickoff."""

    if model.startswith("V6_"):
        blend = float(model.split("_")[1])
        evaluate = lambda rows: evaluate_v6(
            rows, blend
        )
    elif model.startswith("V7_"):
        index = int(model.split("_")[1])
        evaluate = lambda rows: evaluate_v7(
            rows, CONFIGS[index]
        )
    else:
        raise ValueError("Unknown model")

    result = {}
    prefix = []
    previous_count = 0

    dates = sorted({
        m["utcDate"] for m in matches
    })

    for date in dates:
        batch = [
            m for m in matches
            if m["utcDate"] == date
        ]

        prefix.extend(batch)
        rows = evaluate(prefix)

        new_rows = rows[previous_count:]
        previous_count = len(rows)

        # Backtest results do not carry match IDs.
        # Compare ordered probabilities per kickoff.
        result[date] = [
            p for p, _ in new_rows
        ]

    return result


def compare_season(season):
    matches = load_matches(season)
    selections = get_league_models("CL")

    reference = {
        model: get_reference_predictions(
            matches, model
        )
        for model in set(selections.values())
    }

    compared = 0
    mismatches = []

    for match in matches:
        kickoff = match["utcDate"]
        hid = match["homeTeam"]["id"]
        aid = match["awayTeam"]["id"]

        earlier = [
            m for m in matches
            if m["utcDate"] < kickoff
        ]

        if len(earlier) < 10:
            continue

        try:
            live = predict(
                "CL", hid, aid,
                kickoff, earlier
            )
        except ValueError:
            continue

        batch = [
            m for m in matches
            if m["utcDate"] == kickoff
        ]

        position = next(
            (
                i for i, item in enumerate(batch)
                if item["id"] == match["id"]
            ),
            None,
        )

        if position is None:
            continue

        for market, model in selections.items():
            rows = reference[model].get(
                kickoff, []
            )

            if position >= len(rows):
                continue

            expected = rows[position]

            for key in MARKET_KEYS[market]:
                actual = (
                    live["probabilities_percent"][key]
                    / 100
                )

                if abs(actual - expected[key]) > 0.001:
                    mismatches.append(
                        (
                            season,
                            match["id"],
                            market,
                            key,
                            round(actual, 5),
                            round(expected[key], 5),
                        )
                    )

        compared += 1

    print(
        f"{season}: compared={compared}, "
        f"mismatches={len(mismatches)}"
    )

    for item in mismatches[:10]:
        print("MISMATCH:", item)

    if mismatches:
        raise AssertionError(
            f"{season}: {len(mismatches)} mismatches"
        )

    if compared < 20:
        raise AssertionError(
            f"{season}: insufficient comparisons"
        )


class BacktestParityTests(unittest.TestCase):

    def test_2023_parity(self):
        compare_season("2023")

    def test_2024_parity(self):
        compare_season("2024")

    def test_2025_parity(self):
        compare_season("2025")


if __name__ == "__main__":
    unittest.main(verbosity=2)
