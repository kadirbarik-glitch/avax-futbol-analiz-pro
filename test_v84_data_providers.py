"""AVAX V8.4 - Multi-provider data normalization tests."""

import unittest

from v84_data_providers import (
    ProviderDataError,
    normalize_api_football,
    normalize_football_data,
)


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
        match = {
            "fixture": {
                "id": 456,
                "date": "2026-11-08T18:00:00+00:00",
                "status": {"short": "FT"},
            },
            "teams": {
                "home": {"id": 30},
                "away": {"id": 40},
            },
            "goals": {"home": 3, "away": 2},
        }

        result = normalize_api_football(match, "TR")

        self.assertEqual(result.provider, "api-football")
        self.assertEqual(result.match_id, "456")
        self.assertEqual(result.home_goals, 3)
        self.assertEqual(result.away_goals, 2)
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
        match = {
            "fixture": {
                "id": 789,
                "date": "2026-11-09T18:00:00Z",
                "status": {"short": "NS"},
            },
            "teams": {
                "home": {"id": 50},
                "away": {"id": 60},
            },
            "goals": {"home": None, "away": None},
        }

        result = normalize_api_football(match, "TR")

        self.assertIsNone(result.home_goals)
        self.assertIsNone(result.away_goals)
        self.assertEqual(result.status, "NS")


if __name__ == "__main__":
    unittest.main()
