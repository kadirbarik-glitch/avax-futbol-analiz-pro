
"""AVAX V8.4 - Turkey date boundary tests.

Offline tests for UTC to Europe/Istanbul fixture dates.
No API requests and no production changes.
"""

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import v84_daily_fixtures as daily


def make_fixture(fixture_id, kickoff_utc):
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff_utc,
            "status": {"short": "NS"},
        },
        "league": {
            "id": 203,
            "name": "Super Lig",
            "country": "Turkey",
        },
        "teams": {
            "home": {"id": 10, "name": "Home FC"},
            "away": {"id": 20, "name": "Away FC"},
        },
    }


class TurkeyDateBoundaryTests(unittest.TestCase):

    def test_midnight_turkey(self):
        match = daily.normalize_daily_fixture(
            make_fixture(1, "2026-11-09T21:00:00Z")
        )
        self.assertEqual(match["date_tr"], "2026-11-10")
        self.assertEqual(
            match["kickoff_tr"],
            "2026-11-10T00:00:00+03:00",
        )

    def test_0259_turkey(self):
        match = daily.normalize_daily_fixture(
            make_fixture(2, "2026-11-09T23:59:00Z")
        )
        self.assertEqual(match["date_tr"], "2026-11-10")
        self.assertEqual(
            match["kickoff_tr"],
            "2026-11-10T02:59:00+03:00",
        )

    def test_0300_turkey(self):
        match = daily.normalize_daily_fixture(
            make_fixture(3, "2026-11-10T00:00:00Z")
        )
        self.assertEqual(match["date_tr"], "2026-11-10")
        self.assertEqual(
            match["kickoff_tr"],
            "2026-11-10T03:00:00+03:00",
        )

    def test_2359_turkey(self):
        match = daily.normalize_daily_fixture(
            make_fixture(4, "2026-11-10T20:59:00Z")
        )
        self.assertEqual(match["date_tr"], "2026-11-10")
        self.assertEqual(
            match["kickoff_tr"],
            "2026-11-10T23:59:00+03:00",
        )

    def test_next_midnight_excluded(self):
        match = daily.normalize_daily_fixture(
            make_fixture(5, "2026-11-10T21:00:00Z")
        )
        self.assertEqual(match["date_tr"], "2026-11-11")

    def test_two_utc_dates_cover_turkey_day(self):
        selected = date(2026, 11, 10)

        previous_utc = [
            make_fixture(1, "2026-11-09T20:59:00Z"),
            make_fixture(2, "2026-11-09T21:00:00Z"),
            make_fixture(3, "2026-11-09T23:59:00Z"),
        ]

        selected_utc = [
            make_fixture(4, "2026-11-10T00:00:00Z"),
            make_fixture(5, "2026-11-10T20:59:00Z"),
            make_fixture(6, "2026-11-10T21:00:00Z"),
        ]

        with tempfile.TemporaryDirectory() as folder:
            with (
                patch.object(daily, "CACHE_DIR", Path(folder)),
                patch.object(
                    daily,
                    "today_turkey",
                    return_value=selected,
                ),
                patch.dict(
                    "os.environ",
                    {"API_FOOTBALL_KEY": "fake-test-key"},
                ),
                patch.object(
                    daily,
                    "fetch_api_fixtures",
                    side_effect=[previous_utc, selected_utc],
                ) as fetch,
            ):
                result = daily.get_daily_fixtures(
                    selected, force_refresh=True
                )

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(
            fetch.call_args_list[0].args[0],
            date(2026, 11, 9),
        )
        self.assertEqual(
            fetch.call_args_list[1].args[0],
            date(2026, 11, 10),
        )
        self.assertEqual(
            [m["match_id"] for m in result["matches"]],
            ["2", "3", "4", "5"],
        )


if __name__ == "__main__":
    unittest.main()
