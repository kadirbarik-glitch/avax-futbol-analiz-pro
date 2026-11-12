"""Offline tests for the football-data.org daily fixture adapter."""

import unittest
from datetime import date
from unittest.mock import patch

import v84_daily_fixtures as daily


def sample_match(match_id=100, kickoff="2026-11-10T21:30:00Z"):
    return {
        "id": match_id, "utcDate": kickoff, "status": "SCHEDULED",
        "competition": {"code": "PL", "name": "Premier League", "area": {"name": "England"}},
        "homeTeam": {"id": 10, "name": "Home FC"},
        "awayTeam": {"id": 20, "name": "Away FC"},
    }


class DailyFixtureTests(unittest.TestCase):
    def test_valid_date_and_window(self):
        self.assertEqual(daily.validate_date("2026-11-10"), date(2026, 11, 10))
        with self.assertRaises(ValueError):
            daily.validate_date("2026-99-99")
        with patch.object(daily, "today_turkey", return_value=date(2026, 11, 10)):
            self.assertEqual(daily.available_dates(3), ["2026-11-10", "2026-11-11", "2026-11-12"])

    def test_normalizes_same_provider_ids_and_turkish_date(self):
        item = daily.normalize_daily_fixture(sample_match())
        self.assertEqual(item["provider"], "football-data.org")
        self.assertEqual(item["league_id"], "PL")
        self.assertEqual(item["date_tr"], "2026-11-11")
        self.assertEqual(item["kickoff_tr"], "2026-11-11T00:30:00+03:00")

    def test_missing_competition_code_is_rejected(self):
        broken = sample_match()
        broken["competition"]["code"] = ""
        self.assertIsNone(daily.normalize_daily_fixture(broken))

    def test_daily_fixtures_cover_turkish_day_deduplicate_and_sort(self):
        selected = date(2026, 11, 10)
        later = sample_match(101, "2026-11-10T15:00:00Z")
        earlier = sample_match(102, "2026-11-10T12:00:00Z")
        previous_utc = sample_match(103, "2026-11-09T22:00:00Z")
        with patch.object(daily, "today_turkey", return_value=selected), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(daily, "fetch_football_data_fixtures", side_effect=[[previous_utc], [later, earlier, later]]) as fetch, patch.object(daily, "save_cache", side_effect=lambda value, matches: {"date": value.isoformat(), "matches": matches}):
            result = daily.get_daily_fixtures(selected, force_refresh=True)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([item["match_id"] for item in result["matches"]], ["103", "102", "101"])

    def test_cache_avoids_network_and_missing_key_is_clear(self):
        selected = date(2026, 11, 10)
        with patch.object(daily, "today_turkey", return_value=selected), patch.object(daily, "load_cache", return_value={"date": selected.isoformat(), "matches": []}):
            self.assertEqual(daily.get_daily_fixtures(selected)["matches"], [])
        with patch.object(daily, "today_turkey", return_value=selected), patch.object(daily, "load_cache", return_value=None), patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(daily.DailyFixtureError, "FOOTBALL_DATA_API_KEY"):
                    daily.get_daily_fixtures(selected)

    def test_weekly_fixtures_use_one_range_request_and_turkish_dates(self):
        start = date(2026, 11, 10)
        early = sample_match(201, "2026-11-09T22:00:00Z")
        late = sample_match(202, "2026-11-16T20:59:00Z")
        outside = sample_match(203, "2026-11-16T21:00:00Z")
        with patch.object(daily, "today_turkey", return_value=start), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(daily, "fetch_football_data_fixture_range", return_value=[early, late, outside]) as fetch, patch.object(daily, "save_week_cache", side_effect=lambda value, matches, diagnostics: {"start_date": value.isoformat(), "matches": matches, "diagnostics": diagnostics}):
            result = daily.get_weekly_fixtures(start, force_refresh=True)
        fetch.assert_called_once_with(date(2026, 11, 9), date(2026, 11, 16), "test")
        self.assertEqual([item["match_id"] for item in result["matches"]], ["201", "202"])
        self.assertEqual(result["diagnostics"]["provider_match_count"], 3)
        self.assertEqual(result["diagnostics"]["filtered_match_count"], 2)

    def test_week_cache_avoids_range_request(self):
        start = date(2026, 11, 10)
        cached = {"start_date": start.isoformat(), "matches": []}
        with patch.object(daily, "today_turkey", return_value=start), patch.object(daily, "load_week_cache", return_value=cached), patch.object(daily, "fetch_football_data_fixture_range", side_effect=AssertionError("network must not be called")):
            self.assertEqual(daily.get_weekly_fixtures(start), cached)

    def test_weekly_diagnostics_never_log_api_key(self):
        start = date(2026, 11, 10)
        secret = "not-a-real-key"
        with patch.object(daily, "today_turkey", return_value=start), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": secret}), patch.object(daily, "fetch_football_data_fixture_range", return_value=[]), patch.object(daily, "save_week_cache", side_effect=lambda value, matches, diagnostics: {"matches": matches, "diagnostics": diagnostics}), self.assertLogs(daily.LOGGER, level="INFO") as logs:
            daily.get_weekly_fixtures(start, force_refresh=True)
        self.assertNotIn(secret, "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
