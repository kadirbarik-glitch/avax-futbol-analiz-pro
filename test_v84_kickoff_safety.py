
"""AVAX V8.4 - Kickoff safety tests.

Offline tests. No API requests or deployment.
"""

import unittest
from datetime import datetime, timezone, date
from unittest.mock import patch

from v84_daily_app import app, kickoff_is_past


def sample_match(kickoff, status="NS"):
    return {
        "match_id": "123",
        "date_tr": "2026-11-11",
        "kickoff_tr": kickoff,
        "league": "Super Lig",
        "country": "Turkey",
        "home_team": "Home FC",
        "away_team": "Away FC",
        "status": status,
    }


class KickoffSafetyTests(unittest.TestCase):

    def setUp(self):
        self.now = datetime(
            2026, 11, 11, 9, 0,
            tzinfo=timezone.utc,
        )

    def test_future_kickoff(self):
        match = sample_match(
            "2026-11-11T15:00:00+03:00"
        )
        self.assertFalse(
            kickoff_is_past(match, self.now)
        )

    def test_past_kickoff(self):
        match = sample_match(
            "2026-11-11T10:00:00+03:00"
        )
        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_exact_kickoff_time(self):
        match = sample_match(
            "2026-11-11T12:00:00+03:00"
        )
        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_invalid_kickoff(self):
        match = sample_match("invalid-date")
        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_missing_kickoff(self):
        match = sample_match(
            "2026-11-11T12:00:00+03:00"
        )
        del match["kickoff_tr"]

        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_naive_datetime_rejected(self):
        match = sample_match(
            "2026-11-11T12:00:00"
        )
        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_past_ns_match_not_upcoming(self):
        client = app.test_client()

        matches = [
            sample_match(
                "2026-11-11T10:00:00+03:00"
            ),
            sample_match(
                "2026-11-11T18:00:00+03:00"
            ),
        ]

        with (
            patch(
                "v84_daily_app.today_turkey",
                return_value=date(2026, 11, 11),
            ),
            patch(
                "v84_daily_app.get_daily_fixtures",
                return_value={"matches": matches},
            ),
            patch(
                "v84_daily_app.datetime"
            ) as mocked_datetime,
        ):
            mocked_datetime.now.return_value = self.now

            response = client.get("/")

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "Başlangıç saati geçmiş".encode("utf-8"),
            response.data,
        )

        self.assertIn(
            "Başlamamış maçlar (1)".encode("utf-8"),
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
