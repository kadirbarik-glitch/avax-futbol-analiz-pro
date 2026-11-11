
"""AVAX V8.4 - Kickoff safety tests.

Seven offline safety tests.
Development branch only.
No live API calls or deployment.
"""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from v84_daily_app import app, kickoff_is_past


def sample_match(kickoff):
    return {
        "match_id": "12345",
        "date_tr": "2026-11-11",
        "kickoff_tr": kickoff,
        "league_id": 203,
        "league": "Super Lig",
        "country": "Turkey",
        "home_team_id": "10",
        "home_team": "Galatasaray",
        "away_team_id": "20",
        "away_team": "Fenerbahce",
        "status": "NS",
    }


class KickoffSafetyTests(unittest.TestCase):

    def setUp(self):
        self.now = datetime.fromisoformat(
            "2026-11-11T12:00:00+03:00"
        )

    def test_future_match_is_safe(self):
        match = sample_match(
            "2026-11-11T18:00:00+03:00"
        )

        self.assertFalse(
            kickoff_is_past(match, self.now)
        )

    def test_past_match_is_unsafe(self):
        match = sample_match(
            "2026-11-11T10:00:00+03:00"
        )

        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_exact_kickoff_is_unsafe(self):
        match = sample_match(
            "2026-11-11T12:00:00+03:00"
        )

        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_missing_kickoff_is_unsafe(self):
        match = sample_match(
            "2026-11-11T18:00:00+03:00"
        )
        del match["kickoff_tr"]

        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_invalid_kickoff_is_unsafe(self):
        match = sample_match(
            "invalid-date"
        )

        self.assertTrue(
            kickoff_is_past(match, self.now)
        )

    def test_timezone_missing_is_unsafe(self):
        match = sample_match(
            "2026-11-11T18:00:00"
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
                "v84_daily_app.render_template_string",
                return_value="Test page",
            ) as mocked_render,
            patch(
                "v84_daily_app.datetime",
                wraps=datetime,
            ) as mocked_datetime,
        ):
            mocked_datetime.now.return_value = (
                self.now.astimezone(timezone.utc)
            )

            response = client.get("/")

        self.assertEqual(
            response.status_code, 200
        )

        context = mocked_render.call_args.kwargs

        self.assertEqual(
            context["stale"],
            [matches[0]],
        )

        self.assertEqual(
            context["upcoming"],
            [matches[1]],
        )


if __name__ == "__main__":
    unittest.main()
