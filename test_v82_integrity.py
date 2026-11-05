"""AVAX V8.2 - Integrity tests.

Checks chronological order, future leakage,
same-kickoff isolation and repeatability.

Run:
python -m unittest -v test_v82_integrity
"""

import copy
import unittest
from collections import defaultdict

from backtest_v6 import (
    valid,
    evaluate as evaluate_v6,
)
from backtest_v7 import evaluate_v7


CONFIG = (0.08, 0.5, 0.5)


def fixture(mid, date, home, away, hg, ag):
    return {
        "id": mid,
        "utcDate": date,
        "homeTeam": {"id": home},
        "awayTeam": {"id": away},
        "score": {
            "fullTime": {
                "home": hg,
                "away": ag,
            }
        },
    }


def sample_matches():
    matches = []

    # Two independent fixtures at each kickoff.
    # Every team plays only once per kickoff.
    for week in range(1, 13):
        date = f"2025-01-{week:02d}T20:00:00Z"

        matches.extend([
            fixture(
                week * 10 + 1,
                date, 1, 2,
                week % 4,
                (week + 1) % 3,
            ),
            fixture(
                week * 10 + 2,
                date, 3, 4,
                (week + 2) % 4,
                week % 3,
            ),
        ])

    return valid(matches)


def models():
    return {
        "V6": lambda matches: evaluate_v6(
            matches, 0.5
        ),
        "V7": lambda matches: evaluate_v7(
            matches, CONFIG
        ),
    }


def probabilities_only(rows):
    return [
        tuple(
            (key, round(float(value), 10))
            for key, value in sorted(p.items())
        )
        for p, _ in rows
    ]


def grouped_predictions(matches, evaluate):
    """Compare prediction groups by kickoff time.

    No guessed match-ID association is used.
    """

    result = defaultdict(list)
    previous_count = 0
    prefix = []

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

        result[date] = sorted(
            probabilities_only(new_rows)
        )

    return dict(result)


class IntegrityTests(unittest.TestCase):

    def test_valid_sorts_matches(self):
        matches = sample_matches()
        reversed_matches = list(reversed(matches))

        self.assertEqual(
            [m["id"] for m in matches],
            [
                m["id"]
                for m in valid(reversed_matches)
            ],
        )

    def test_future_results_do_not_change_past(self):
        matches = sample_matches()
        cutoff = "2025-01-09T20:00:00Z"

        changed = copy.deepcopy(matches)

        for match in changed:
            if match["utcDate"] >= cutoff:
                match["score"]["fullTime"]["home"] = 9
                match["score"]["fullTime"]["away"] = 0

        earlier = [
            m for m in matches
            if m["utcDate"] < cutoff
        ]

        for name, evaluate in models().items():
            with self.subTest(model=name):
                baseline = evaluate(earlier)
                modified = evaluate(changed)

                self.assertGreater(
                    len(baseline), 0
                )

                self.assertEqual(
                    probabilities_only(baseline),
                    probabilities_only(
                        modified[:len(baseline)]
                    ),
                )

    def test_same_kickoff_order_invariance(self):
        matches = sample_matches()

        reordered = []
        for i in range(0, len(matches), 2):
            reordered.extend(
                reversed(matches[i:i + 2])
            )

        for name, evaluate in models().items():
            with self.subTest(model=name):
                original = grouped_predictions(
                    matches, evaluate
                )
                shuffled = grouped_predictions(
                    reordered, evaluate
                )

                self.assertTrue(original)
                self.assertEqual(
                    original, shuffled
                )

    def test_same_kickoff_result_isolation(self):
        matches = sample_matches()
        changed = copy.deepcopy(matches)

        target_date = "2025-01-09T20:00:00Z"

        for match in changed:
            if (
                match["utcDate"] == target_date
                and match["id"] % 10 == 1
            ):
                match["score"]["fullTime"]["home"] = 9
                match["score"]["fullTime"]["away"] = 9

        for name, evaluate in models().items():
            with self.subTest(model=name):
                first = grouped_predictions(
                    matches, evaluate
                )
                second = grouped_predictions(
                    changed, evaluate
                )

                self.assertTrue(first[target_date])
                self.assertEqual(
                    first[target_date],
                    second[target_date],
                )

    def test_normalization(self):
        matches = sample_matches()
        reversed_matches = list(reversed(matches))

        normalized = valid(reversed_matches)

        for name, evaluate in models().items():
            with self.subTest(model=name):
                self.assertEqual(
                    evaluate(matches),
                    evaluate(normalized),
                )

    def test_repeatability(self):
        matches = sample_matches()

        for name, evaluate in models().items():
            with self.subTest(model=name):
                first = evaluate(matches)
                second = evaluate(matches)

                self.assertEqual(first, second)

    def test_input_is_not_mutated(self):
        matches = sample_matches()
        before = copy.deepcopy(matches)

        for name, evaluate in models().items():
            with self.subTest(model=name):
                evaluate(matches)
                self.assertEqual(matches, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
