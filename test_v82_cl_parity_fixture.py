"""Deterministic CL backtest/live parity test without real API data.

This fixture protects parity logic in ordinary CI. It is synthetic and
must not be interpreted as historical Champions League evidence.
"""

import unittest

from backtest_v6 import valid
from test_v82_backtest_parity import (
    MARKET_KEYS,
    TOLERANCE,
    eligible_matches,
    reference_by_match_id,
)
from v8_live_engine import predict
from v8_models import get_league_models


def fixture(mid, date, home, away, home_goals, away_goals):
    return {
        "id": mid,
        "utcDate": date,
        "status": "FINISHED",
        "homeTeam": {"id": home},
        "awayTeam": {"id": away},
        "score": {
            "fullTime": {
                "home": home_goals,
                "away": away_goals,
            }
        },
    }


def sample_matches():
    matches = []

    for day in range(1, 15):
        date = f"2025-09-{day:02d}T20:00:00Z"
        matches.extend(
            [
                fixture(
                    day * 10 + 1, date, 1, 2,
                    day % 4, (day + 1) % 3,
                ),
                fixture(
                    day * 10 + 2, date, 3, 4,
                    (day + 2) % 4, day % 3,
                ),
            ]
        )

    return valid(matches)


class ChampionsLeagueFixtureParityTests(unittest.TestCase):

    def test_live_engine_matches_backtest_references(self):
        matches = sample_matches()
        eligible = eligible_matches(matches)
        selected = get_league_models("CL")

        self.assertGreaterEqual(len(eligible), 20)
        self.assertEqual(set(selected), set(MARKET_KEYS))

        references = {
            model: reference_by_match_id(
                matches, model, eligible
            )
            for model in set(selected.values())
        }

        for match in eligible:
            with self.subTest(match_id=match["id"]):
                kickoff = match["utcDate"]
                earlier = [
                    item for item in matches
                    if item["utcDate"] < kickoff
                ]
                live = predict(
                    "CL",
                    match["homeTeam"]["id"],
                    match["awayTeam"]["id"],
                    kickoff,
                    earlier,
                )

                for market, model in selected.items():
                    self.assertEqual(
                        live["models"][market]["model"], model
                    )
                    reference = references[model][match["id"]]

                    for key in MARKET_KEYS[market]:
                        actual = (
                            live["probabilities_percent"][key]
                            / 100.0
                        )
                        self.assertAlmostEqual(
                            actual,
                            reference[key],
                            delta=TOLERANCE,
                        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
