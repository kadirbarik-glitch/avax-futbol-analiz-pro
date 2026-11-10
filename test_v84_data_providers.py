"""AVAX V8.4 - Multi-provider data normalization tests.

Includes normal, awarded, walkover and postponed match tests.
No API calls or production changes.
"""

import unittest

from v84_data_providers import (
    ProviderDataError,
    normalize_api_football,
    normalize_football_data,
)


def make_api_fixture(status="FT", home_goals=2, away_goals=1):
    return {
        "fixture": {
            "id": 456,
            "date": "2026-11-08T18:00:00+00:00",
            "status": {"short": status},
        },
        "teams": {
            "home": {"id": 30},
            "away": {"id": 40},
        },
        "goals": {
            "home": home_goals,
            "away": away_goals,
        },
    }


class ProviderTests(unittest.TestCase):

    def test_football_data_finished_match(self):
        match = {
            "id": 123,
            "utcDate": "2026-11-08T18:00:00Z",
            "status": "FINISHED",
            "homeTeam": {"id": 10},
            "awayTeam": {"id": 20},
            "score": {
                "fullTime": {"home": 2, "away": 1}
            },
        }

        result = normalize_football_data(match, "PL")

        self.assertEqual(result.provider, "football-data.org")
        self.assertEqual(result.match_id, "123")
        self.assertEqual(result.home_goals, 2)
        self.assertEqual(result.away_goals, 1)
        self.assertEqual(result.status, "FINISHED")

    def test_api_football_finished_match(self):
        result = normalize_api_football(
            make_api_fixture(), "TR"
        )

        self.assertEqual(result.provider, "api-football")
        self.assertEqual(result.match_id, "456")
        self.assertEqual(result.home_goals, 2)
        self.assertEqual(result.away_goals, 1)
        self.assertEqual(result.status, "FT")

    def test_missing_team_id_rejected(self):
        match = {
            "id": 123,
            "utcDate": "2026-11-08T18:00:00Z",
            "status": "FINISHED",
            "homeTeam": {},
            "awayTeam": {"id": 20},
        }

        with self.assertRaises(ProviderDataError):
            normalize_football_data(match, "PL")

    def test_missing_api_football_fixture_rejected(self):
        with self.assertRaises(ProviderDataError):
            normalize_api_football({}, "TR")

    def test_scheduled_match_without_score(self):
        result = normalize_api_football(
            make_api_fixture("NS", None, None), "TR"
        )

        self.assertIsNone(result.home_goals)
        self.assertIsNone(result.away_goals)
        self.assertEqual(result.status, "NS")

    def test_awarded_match_status_preserved(self):
        result = normalize_api_football(
            make_api_fixture("AWD", 3, 0), "TR"
        )

        self.assertEqual(result.status, "AWD")
        self.assertEqual(result.home_goals, 3)
        self.assertEqual(result.away_goals, 0)

    def test_walkover_match_status_preserved(self):
        result = normalize_api_football(
            make_api_fixture("WO", 0, 3), "TR"
        )

        self.assertEqual(result.status, "WO")
        self.assertEqual(result.home_goals, 0)
        self.assertEqual(result.away_goals, 3)

    def test_postponed_match_status_preserved(self):
        result = normalize_api_football(
            make_api_fixture("PST", None, None), "TR"
        )

        self.assertEqual(result.status, "PST")
        self.assertIsNone(result.home_goals)
        self.assertIsNone(result.away_goals)

    def test_cancelled_match_status_preserved(self):
        result = normalize_api_football(
            make_api_fixture("CANC", None, None), "TR"
        )

        self.assertEqual(result.status, "CANC")
        self.assertIsNone(result.home_goals)
        self.assertIsNone(result.away_goals)


if __name__ == "__main__":
    unittest.main()
