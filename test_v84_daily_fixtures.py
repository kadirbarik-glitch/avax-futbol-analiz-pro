
"""AVAX V8.4 - Daily fixture tests.

Offline tests. No real API requests or production changes.
"""

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import v84_daily_fixtures as daily


def sample_fixture(
    fixture_id=100,
    kickoff="2026-11-10T21:30:00+00:00",
    status="NS",
):
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff,
            "status": {"short": status},
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


class DailyFixtureTests(unittest.TestCase):

    def test_valid_date(self):
        self.assertEqual(
            daily.validate_date("2026-11-10"),
            date(2026, 11, 10),
        )

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            daily.validate_date("2026-99-99")

    def test_available_dates(self):
        with patch.object(
            daily, "today_turkey",
            return_value=date(2026, 11, 10),
        ):
            dates = daily.available_dates(3)

        self.assertEqual(
            dates,
            ["2026-11-10", "2026-11-11", "2026-11-12"],
        )

    def test_available_dates_limit(self):
        with self.assertRaises(ValueError):
            daily.available_dates(31)

    def test_turkey_timezone(self):
        match = daily.normalize_daily_fixture(
            sample_fixture()
        )

        self.assertEqual(
            match["date_tr"], "2026-11-11"
        )
        self.assertEqual(
            match["kickoff_tr"],
            "2026-11-11T00:30:00+03:00",
        )

    def test_invalid_fixture_rejected(self):
        self.assertIsNone(
            daily.normalize_daily_fixture({})
        )

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(
                daily, "CACHE_DIR", Path(folder)
            ):
                saved = daily.save_cache(
                    "2026-11-10", [{"match_id": "100"}]
                )
                loaded = daily.load_cache("2026-11-10")

        self.assertEqual(saved, loaded)

    def test_cache_expired(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(
                daily, "CACHE_DIR", Path(folder)
            ):
                saved = daily.save_cache(
                    "2026-11-10", []
                )

                old_time = (
                    datetime.now(timezone.utc)
                    - timedelta(hours=2)
                ).isoformat()

                path = daily.cache_path("2026-11-10")
                saved["fetched_at"] = old_time

                import json
                path.write_text(
                    json.dumps(saved), encoding="utf-8"
                )

                self.assertIsNone(
                    daily.load_cache("2026-11-10")
                )

    def test_daily_fixtures_sorted_and_deduplicated(self):
        selected = date(2026, 11, 10)

        first = sample_fixture(
            101, "2026-11-10T15:00:00+00:00"
        )
        second = sample_fixture(
            102, "2026-11-10T12:00:00+00:00"
        )
        next_day = sample_fixture(
            103, "2026-11-10T22:00:00+00:00"
        )

        with tempfile.TemporaryDirectory() as folder:
            with (
                patch.object(
                    daily, "CACHE_DIR", Path(folder)
                ),
                patch.object(
                    daily, "today_turkey",
                    return_value=selected,
                ),
                patch.dict(
                    "os.environ",
                    {"API_FOOTBALL_KEY": "fake-test-key"},
                ),
                patch.object(
                    daily, "fetch_api_fixtures",
                    side_effect=[
                        [first],
                        [first, second, next_day],
                    ],
                ) as fetch,
            ):
                result = daily.get_daily_fixtures(
                    selected, force_refresh=True
                )

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(
            [m["match_id"] for m in result["matches"]],
            ["102", "101"],
        )

    def test_cache_avoids_api_requests(self):
        selected = date(2026, 11, 10)

        with tempfile.TemporaryDirectory() as folder:
            with (
                patch.object(
                    daily, "CACHE_DIR", Path(folder)
                ),
                patch.object(
                    daily, "today_turkey",
                    return_value=selected,
                ),
                patch.object(
                    daily, "fetch_api_fixtures",
                    side_effect=AssertionError(
                        "API must not be called"
                    ),
                ),
            ):
                daily.save_cache(selected, [])
                result = daily.get_daily_fixtures(selected)

        self.assertEqual(result["matches"], [])


if __name__ == "__main__":
    unittest.main()
