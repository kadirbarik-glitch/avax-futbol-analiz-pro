"""AVAX V8.4 - Daily Match Center UI tests.

Offline Flask tests. No API requests or live deployment.
"""

import unittest
from datetime import date
from unittest.mock import patch

from v84_daily_app import app


def sample_match():
    return {
        "match_id": "12345",
        "date_tr": "2026-11-10",
        "kickoff_tr": "2026-11-10T20:00:00+03:00",
        "league_id": 203,
        "league": "Super Lig",
        "country": "Turkey",
        "home_team_id": "10",
        "home_team": "Galatasaray",
        "away_team_id": "20",
        "away_team": "Fenerbahce",
        "status": "NS",
    }


class DailyAppTests(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.today_patch = patch(
            "v84_daily_app.today_turkey",
            return_value=date(2026, 11, 10),
        )
        self.today_patch.start()
        self.addCleanup(self.today_patch.stop)

    def test_home_page_opens(self):
        with patch(
            "v84_daily_app.get_daily_fixtures",
            return_value={
                "date": "2026-11-10",
                "matches": [sample_match()],
            },
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"AVAX FUTBOL ANAL",
            response.data,
        )
        self.assertIn(
            b"Galatasaray",
            response.data,
        )

    def test_country_filter(self):
        other = {
            **sample_match(),
            "match_id": "999",
            "country": "Germany",
            "league": "Bundesliga",
        }

        with patch(
            "v84_daily_app.get_daily_fixtures",
            return_value={
                "date": "2026-11-10",
                "matches": [sample_match(), other],
            },
        ):
            response = self.client.get(
                "/?country=Turkey"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Galatasaray",
            response.data,
        )
        self.assertNotIn(
            b"Bundesliga",
            response.data,
        )

    def test_league_filter(self):
        other = {
            **sample_match(),
            "match_id": "998",
            "league": "Turkish Cup",
        }

        with patch(
            "v84_daily_app.get_daily_fixtures",
            return_value={
                "date": "2026-11-10",
                "matches": [sample_match(), other],
            },
        ):
            response = self.client.get(
                "/?league=Super+Lig"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Super Lig",
            response.data,
        )
        self.assertNotIn(
            b"Turkish Cup",
            response.data,
        )

    def test_invalid_date_warning(self):
        response = self.client.get(
            "/?date=2026-99-99"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Date must be YYYY-MM-DD",
            response.data,
        )

    def test_empty_match_list(self):
        with patch(
            "v84_daily_app.get_daily_fixtures",
            return_value={
                "date": "2026-11-10",
                "matches": [],
            },
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "gösterilecek maç bulunamadı".encode("utf-8"),
            response.data,
        )

    def test_api_error_is_displayed(self):
        from v84_daily_fixtures import DailyFixtureError

        with patch(
            "v84_daily_app.get_daily_fixtures",
            side_effect=DailyFixtureError(
                "API unavailable"
            ),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"API unavailable",
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
