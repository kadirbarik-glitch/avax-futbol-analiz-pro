"""AVAX V8.4 - Daily Match Center UI tests.

Offline Flask tests.
No real API requests or deployment.
"""

import unittest
from datetime import date
from unittest.mock import patch

from v84_daily_app import app, classify_match
from v84_daily_fixtures import DailyFixtureError


def sample_match(
    match_id="12345",
    status="NS",
    league="Super Lig",
    country="Turkey",
    home="Galatasaray",
    away="Fenerbahce",
):
    return {
        "match_id": match_id,
        "date_tr": "2026-11-10",
        "kickoff_tr": "2026-11-10T20:00:00+03:00",
        "league_id": 203,
        "league": league,
        "country": country,
        "home_team_id": "10",
        "home_team": home,
        "away_team_id": "20",
        "away_team": away,
        "status": status,
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

    def get_page(self, matches, query="/"):
        with patch(
            "v84_daily_app.get_daily_fixtures",
            return_value={
                "date": "2026-11-10",
                "matches": matches,
            },
        ):
            return self.client.get(query)

    def test_home_page_opens(self):
        response = self.get_page([sample_match()])

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AVAX FUTBOL ANAL", response.data)
        self.assertIn(b"Galatasaray", response.data)

    def test_country_filter(self):
        other = sample_match(
            match_id="999",
            country="Germany",
            league="Bundesliga",
            home="Bayern Munich",
            away="Dortmund",
        )

        response = self.get_page(
            [sample_match(), other],
            "/?country=Turkey",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Galatasaray", response.data)
        self.assertNotIn(b"Bayern Munich", response.data)
        self.assertNotIn(b"Dortmund", response.data)

    def test_league_filter(self):
        other = sample_match(
            match_id="998",
            league="Turkish Cup",
            home="Besiktas",
            away="Trabzonspor",
        )

        response = self.get_page(
            [sample_match(), other],
            "/?league=Super+Lig",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Galatasaray", response.data)
        self.assertIn(b"Fenerbahce", response.data)
        self.assertNotIn(b"Besiktas", response.data)
        self.assertNotIn(b"Trabzonspor", response.data)

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
        response = self.get_page([])

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Başlamamış maç bulunamadı".encode("utf-8"),
            response.data,
        )

    def test_api_error_is_displayed(self):
        with patch(
            "v84_daily_app.get_daily_fixtures",
            side_effect=DailyFixtureError(
                "API unavailable"
            ),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"API unavailable", response.data)

    def test_analysis_route_returns_guarded_bridge_result(self):
        match = sample_match()
        match.update({"provider": "football-data.org", "league_id": "PL"})
        expected = {"eligible": True, "analysis_ready": True, "prediction": {}}
        with patch("v84_daily_app.get_daily_fixtures", return_value={"date": "2026-11-10", "matches": [match]}), patch("v84_analysis_bridge.prepare_analysis", return_value=expected):
            response = self.client.get("/analysis/12345?date=2026-11-10")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

    def test_analysis_route_rejects_unknown_match(self):
        with patch("v84_daily_app.get_daily_fixtures", return_value={"date": "2026-11-10", "matches": []}):
            response = self.client.get("/analysis/missing?date=2026-11-10")
        self.assertEqual(response.status_code, 404)

    def test_upcoming_status(self):
        self.assertEqual(
            classify_match("NS"), "upcoming"
        )
        self.assertEqual(
            classify_match("TBD"), "upcoming"
        )

    def test_live_status(self):
        for status in (
            "1H", "HT", "2H", "ET", "BT", "P", "INT", "LIVE"
        ):
            with self.subTest(status=status):
                self.assertEqual(
                    classify_match(status), "live"
                )

    def test_finished_status(self):
        for status in ("FT", "AET", "PEN"):
            with self.subTest(status=status):
                self.assertEqual(
                    classify_match(status), "finished"
                )

    def test_postponed_status(self):
        for status in (
            "PST", "CANC", "ABD", "SUSP", "AWD", "WO"
        ):
            with self.subTest(status=status):
                self.assertEqual(
                    classify_match(status), "postponed"
                )

    def test_unknown_status(self):
        self.assertEqual(
            classify_match("UNKNOWN"), "other"
        )


if __name__ == "__main__":
    unittest.main()
