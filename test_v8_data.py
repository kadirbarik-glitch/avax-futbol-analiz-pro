
"""AVAX V8 veri baglantisi cevrimdisi testleri.

Gercek futbol API'sine istek gondermez.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import v8_data


class TestV8Data(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.kickoff = (
            self.now + timedelta(days=2)
        ).isoformat()

        self.old_date = (
            self.now - timedelta(days=2)
        ).isoformat()

        self.future_date = (
            self.now + timedelta(days=3)
        ).isoformat()

        self.matches = [
            {
                "id": 1,
                "utcDate": self.old_date,
                "status": "FINISHED",
            },
            {
                "id": 2,
                "utcDate": self.future_date,
                "status": "FINISHED",
            },
            {
                "id": 3,
                "utcDate": self.old_date,
                "status": "SCHEDULED",
            },
        ]

    def test_history_filters(self):
        with (
            patch.object(
                v8_data, "api_get",
                return_value=(
                    {"matches": self.matches}, None
                )
            ) as api,
            patch.object(
                v8_data, "valid",
                side_effect=lambda rows: rows
            )
        ):
            result = v8_data.league_history(
                "PL", self.kickoff
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)
        api.assert_called_once()

    def test_api_error(self):
        with patch.object(
            v8_data, "api_get",
            return_value=(None, "HTTP 429")
        ):
            with self.assertRaises(RuntimeError):
                v8_data.league_history(
                    "PL", self.kickoff
                )

    def test_unsupported_league(self):
        with self.assertRaises(ValueError):
            v8_data.league_history(
                "UNKNOWN", self.kickoff
            )

    def test_live_prediction_connection(self):
        
        fake_history = [
            {
                "id": i,
                "utcDate": (
                    self.now - timedelta(days=i + 1)
                ).isoformat(),
                "homeTeam": {"id": 1},
                "awayTeam": {"id": 2},
            }
            for i in range(25)
        ]


        fake_result = {
            "probabilities_percent": {
                "home": 45,
                "draw": 27,
                "away": 28,
                "over25": 54,
                "btts": 51,
            }
        }

        with (
            patch.object(
                v8_data, "league_history",
                return_value=fake_history
            ),
            patch.object(
                v8_data, "predict",
                return_value=fake_result.copy()
            ) as predictor
        ):
            result = v8_data.analyze_match(
                "PL", 1, 2, self.kickoff
            )

        self.assertEqual(
            result["historical_matches_loaded"], 25
        )
        self.assertFalse(
            result["live_odds_included"]
        )
        predictor.assert_called_once()

    def test_started_match_rejected(self):
        past = (
            self.now - timedelta(hours=1)
        ).isoformat()

        with self.assertRaises(ValueError):
            v8_data.analyze_match(
                "PL", 1, 2, past
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
