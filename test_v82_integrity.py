
"""AVAX V8.2 - Chronology and data leakage integrity tests.

Run: python -m unittest -v test_v82_integrity
No API key required.
"""

import copy
import unittest
from unittest.mock import patch

import backtest_v6
import backtest_v7

CONFIG = (0.08, 0.5, 0.5)


def fixture(mid, kickoff, home, away, hg, ag):
    return {
        "id": mid,
        "utcDate": kickoff,
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

    for week in range(1, 9):
        date = f"2025-01-{week:02d}T20:00:00Z"

        matches.extend([
            fixture(
                week * 10 + 1, date, 1, 2,
                week % 4, (week + 1) % 3
            ),
            fixture(
                week * 10 + 2, date, 3, 4,
                (week + 2) % 4, week % 3
            ),
            fixture(
                week * 10 + 3, date, 1, 3,
                week % 3, (week + 2) % 3
            ),
        ])

    return backtest_v6.valid(matches)


def capture_predictions(matches, model):
    """Capture predictions against the actual match ID."""

    captured = {}
    current_match = [None]

    original_v6 = backtest_v6.probabilities
    original_v7 = backtest_v7.probabilities

    def record_v6(h, a):
        prediction = original_v6(h, a)
        if current_match[0] is not None:
            captured[current_match[0]] = prediction.copy()
        return prediction

    def record_v7(h, a):
        prediction = original_v7(h, a)
        if current_match[0] is not None:
            captured[current_match[0]] = prediction.copy()
        return prediction

    original_expected = backtest_v6.expected
    original_estimate = backtest_v7.estimate

    def tracked_expected(history, hid, aid, blend):
        current_match[0] = next(
            (
                m["id"] for m in matches
                if m["homeTeam"]["id"] == hid
                and m["awayTeam"]["id"] == aid
                and m["id"] not in captured
            ),
            None,
        )
        return original_expected(history, hid, aid, blend)

    def tracked_estimate(
        history, hid, aid, league_home, league_away, config
    ):
        current_match[0] = next(
            (
                m["id"] for m in matches
                if m["homeTeam"]["id"] == hid
                and m["awayTeam"]["id"] == aid
                and m["id"] not in captured
            ),
            None,
        )
        return original_estimate(
            history, hid, aid,
            league_home, league_away, config
        )

    if model == "V6":
        with patch.object(
            backtest_v6, "expected",
            side_effect=tracked_expected
        ), patch.object(
            backtest_v6, "probabilities",
            side_effect=record_v6
        ):
            backtest_v6.evaluate(matches, 0.5)
    else:
        with patch.object(
            backtest_v7, "estimate",
            side_effect=tracked_estimate
        ), patch.object(
            backtest_v7, "probabilities",
            side_effect=record_v7
        ):
            backtest_v7.evaluate_v7(matches, CONFIG)

    return captured


class IntegrityTests(unittest.TestCase):

    def test_valid_sorts_matches(self):
        matches = sample_matches()
        reversed_matches = list(reversed(matches))

        self.assertEqual(
            [m["id"] for m in backtest_v6.valid(reversed_matches)],
            [m["id"] for m in matches],
        )

    def test_same_kickoff_order_invariance(self):
        matches = sample_matches()
        reordered = []

        for i in range(0, len(matches), 3):
            reordered.extend(reversed(matches[i:i + 3]))

        for model in ("V6", "V7"):
            with self.subTest(model=model):
                first = capture_predictions(matches, model)
                second = capture_predictions(reordered, model)

                self.assertTrue(first)
                self.assertEqual(
                    set(first),
                    set(second),
                )

                for mid in first:
                    for market in first[mid]:
                        self.assertAlmostEqual(
                            first[mid][market],
                            second[mid][market],
                            places=10,
                            msg=f"{model} match={mid} market={market}",
                        )

    def test_future_results_do_not_change_past(self):
        matches = sample_matches()
        cutoff = "2025-01-06T20:00:00Z"

        changed = copy.deepcopy(matches)

        for m in changed:
            if m["utcDate"] >= cutoff:
                m["score"]["fullTime"]["home"] = 9
                m["score"]["fullTime"]["away"] = 0

        for model in ("V6", "V7"):
            with self.subTest(model=model):
                first = capture_predictions(matches, model)
                second = capture_predictions(changed, model)

                earlier_ids = [
                    m["id"] for m in matches
                    if m["utcDate"] < cutoff
                    and m["id"] in first
                ]

                self.assertTrue(earlier_ids)

                for mid in earlier_ids:
                    self.assertIn(mid, second)

                    for market in first[mid]:
                        self.assertAlmostEqual(
                            first[mid][market],
                            second[mid][market],
                            places=10,
                        )

    def test_unsorted_input_requires_normalization(self):
        matches = sample_matches()
        normalized = backtest_v6.valid(
            list(reversed(matches))
        )

        self.assertEqual(
            [m["id"] for m in matches],
            [m["id"] for m in normalized],
        )

    def test_input_is_not_mutated(self):
        matches = sample_matches()
        before = copy.deepcopy(matches)

        for model in ("V6", "V7"):
            with self.subTest(model=model):
                capture_predictions(matches, model)
                self.assertEqual(matches, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
