"""AVAX V8.2 - Leakage and chronological integrity tests.

Run: python test_v82_integrity.py
No API key or cached match data required.
"""

import copy
import unittest

from backtest_v6 import evaluate as evaluate_v6, valid
from backtest_v7 import evaluate_v7

CONFIG = (0.08, 0.5, 0.5)


def fixture(mid, kickoff, home, away, hg, ag):
    return {
        "id": mid,
        "utcDate": kickoff,
        "homeTeam": {"id": home},
        "awayTeam": {"id": away},
        "score": {"fullTime": {"home": hg, "away": ag}},
    }


def sample_matches():
    matches = []
    for week in range(1, 9):
        date = f"2025-01-{week:02d}T20:00:00Z"
        matches.append(fixture(
            week * 10 + 1, date, 1, 2,
            week % 4, (week + 1) % 3
        ))
        matches.append(fixture(
            week * 10 + 2, date, 3, 4,
            (week + 2) % 4, week % 3
        ))
        matches.append(fixture(
            week * 10 + 3, date, 1, 3,
            week % 3, (week + 2) % 3
        ))
    return valid(matches)


def predictions(rows):
    return [
        {key: round(value, 12) for key, value in p.items()}
        for p, _ in rows
    ]


class IntegrityTests(unittest.TestCase):

    def models(self):
        return (
            ("V6", lambda m: evaluate_v6(m, 0.5)),
            ("V7", lambda m: evaluate_v7(m, CONFIG)),
        )

    def test_valid_sorts_matches(self):
        matches = sample_matches()
        reversed_matches = list(reversed(matches))
        self.assertEqual(
            [m["id"] for m in valid(reversed_matches)],
            [m["id"] for m in matches],
        )

    def test_future_results_do_not_change_past(self):
        matches = sample_matches()
        cutoff = 6
        earlier = [
            m for m in matches
            if m["utcDate"] < "2025-01-06T20:00:00Z"
        ]
        changed = copy.deepcopy(matches)

        for m in changed:
            if m["utcDate"] >= "2025-01-06T20:00:00Z":
                m["score"]["fullTime"]["home"] = 9
                m["score"]["fullTime"]["away"] = 0

        for name, model in self.models():
            with self.subTest(model=name):
                baseline = model(earlier)
                modified = model(changed)
                self.assertGreater(len(baseline), 0)
                self.assertEqual(
                    predictions(baseline),
                    predictions(modified[:len(baseline)]),
                )

    def test_same_kickoff_order_invariance(self):
        matches = sample_matches()
        reordered = []
        for i in range(0, len(matches), 3):
            reordered.extend(reversed(matches[i:i + 3]))

        for name, model in self.models():
            with self.subTest(model=name):
                original = model(matches)
                shuffled = model(reordered)
                self.assertEqual(
                    len(original), len(shuffled)
                )
                # Compare prediction groups without relying on
                # their internal order within the kickoff batch.
                def canonical(rows):
                    return sorted(
                        tuple(sorted(p.items()))
                        for p, _ in rows
                    )
                self.assertEqual(
                    canonical(original),
                    canonical(shuffled),
                )

    def test_unsorted_input_requires_normalization(self):
        matches = sample_matches()
        unsorted = list(reversed(matches))
        normalized = valid(unsorted)

        for name, model in self.models():
            with self.subTest(model=name):
                self.assertEqual(
                    model(matches),
                    model(normalized),
                )

    def test_input_is_not_mutated(self):
        matches = sample_matches()
        before = copy.deepcopy(matches)
        for name, model in self.models():
            with self.subTest(model=name):
                model(matches)
                self.assertEqual(matches, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
