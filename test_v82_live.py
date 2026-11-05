"""AVAX V8.2 - Live engine integration tests.

Run:
    python -m unittest -v test_v82_live

No API key or network connection required.
"""

import copy
import unittest

from backtest_v6 import valid
from v8_models import MODEL_SELECTIONS, get_league_models
from v8_live_engine import LEAGUES, build_histories, predict


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

    for day in range(1, 13):
        date = f"2025-01-{day:02d}T20:00:00Z"

        matches.extend([
            fixture(
                day * 10 + 1, date,
                1, 2,
                day % 4, (day + 1) % 3,
            ),
            fixture(
                day * 10 + 2, date,
                3, 4,
                (day + 2) % 4, day % 3,
            ),
        ])

    return valid(matches)


KICKOFF = "2025-01-13T20:00:00Z"


class LiveEngineTests(unittest.TestCase):

    def test_six_leagues_supported(self):
        expected = {
            "PL", "PD", "SA",
            "BL1", "FL1", "CL",
        }

        self.assertEqual(set(LEAGUES), expected)
        self.assertEqual(
            set(MODEL_SELECTIONS), expected
        )

    def test_champions_league_models(self):
        selected = get_league_models("CL")

        self.assertEqual(
            selected["match_result"], "V7_15"
        )
        self.assertEqual(
            selected["over25"], "V7_03"
        )
        self.assertEqual(
            selected["btts"], "V7_17"
        )

    def test_all_leagues_produce_predictions(self):
        matches = sample_matches()

        for league in LEAGUES:
            with self.subTest(league=league):
                result = predict(
                    league, 1, 2,
                    KICKOFF, matches
                )

                self.assertEqual(
                    result["league"], league
                )

                self.assertGreater(
                    result["matches_in_history"], 0
                )

                probabilities = (
                    result["probabilities_percent"]
                )

                for value in probabilities.values():
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, 100)

                self.assertAlmostEqual(
                    probabilities["home"]
                    + probabilities["draw"]
                    + probabilities["away"],
                    100,
                    delta=0.05,
                )

                self.assertAlmostEqual(
                    probabilities["over25"]
                    + probabilities["under25"],
                    100,
                    delta=0.01,
                )

                self.assertAlmostEqual(
                    probabilities["btts"]
                    + probabilities["no_btts"],
                    100,
                    delta=0.01,
                )

    def test_future_results_do_not_change_prediction(self):
        matches = sample_matches()

        original = predict(
            "CL", 1, 2, KICKOFF, matches
        )

        changed = copy.deepcopy(matches)

        changed.extend([
            fixture(
                9991,
                "2025-01-14T20:00:00Z",
                1, 2, 9, 0
            ),
            fixture(
                9992,
                "2025-01-15T20:00:00Z",
                3, 4, 0, 9
            ),
        ])

        modified = predict(
            "CL", 1, 2, KICKOFF, changed
        )

        self.assertEqual(
            original["probabilities_percent"],
            modified["probabilities_percent"],
        )

    def test_same_kickoff_results_excluded(self):
        matches = sample_matches()

        original = predict(
            "CL", 1, 2, KICKOFF, matches
        )

        changed = copy.deepcopy(matches)

        changed.append(
            fixture(
                9993, KICKOFF,
                3, 4, 9, 9
            )
        )

        modified = predict(
            "CL", 1, 2, KICKOFF, changed
        )

        self.assertEqual(
            original["probabilities_percent"],
            modified["probabilities_percent"],
        )

    def test_input_order_does_not_change_prediction(self):
        matches = sample_matches()

        original = predict(
            "CL", 1, 2, KICKOFF, matches
        )

        reordered = list(reversed(matches))

        modified = predict(
            "CL", 1, 2, KICKOFF, reordered
        )

        self.assertEqual(
            original["probabilities_percent"],
            modified["probabilities_percent"],
        )

    def test_input_is_not_mutated(self):
        matches = sample_matches()
        before = copy.deepcopy(matches)

        predict("CL", 1, 2, KICKOFF, matches)

        self.assertEqual(matches, before)

    def test_insufficient_history_rejected(self):
        with self.assertRaises(ValueError):
            predict(
                "CL", 1, 2,
                KICKOFF, []
            )

    def test_same_team_rejected(self):
        with self.assertRaises(ValueError):
            predict(
                "CL", 1, 1,
                KICKOFF, sample_matches()
            )

    def test_unsupported_league_rejected(self):
        with self.assertRaises(ValueError):
            predict(
                "UNKNOWN", 1, 2,
                KICKOFF, sample_matches()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
