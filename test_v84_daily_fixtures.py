"""Offline tests for the football-data.org daily fixture adapter."""

import unittest
from datetime import date
import time
from unittest.mock import MagicMock, patch

import v84_daily_fixtures as daily


def sample_match(match_id=100, kickoff="2026-11-10T21:30:00Z"):
    return {
        "id": match_id, "utcDate": kickoff, "status": "SCHEDULED",
        "competition": {"code": "PL", "name": "Premier League", "area": {"name": "England"}},
        "homeTeam": {"id": 10, "name": "Home FC"},
        "awayTeam": {"id": 20, "name": "Away FC"},
    }


class DailyFixtureTests(unittest.TestCase):

    def test_process_lock_allows_only_one_weekly_refresher(self):
        start = date(2026, 11, 10)
        path = MagicMock()
        path.stat.return_value.st_mtime = time.time()
        with patch.object(daily, "week_cache_lock_path", return_value=path), patch.object(daily.os, "open", side_effect=[12, FileExistsError]), patch.object(daily.os, "write"), patch.object(daily.os, "close"):
            first = daily.acquire_week_cache_lock(start)
            self.assertIsNotNone(first)
            with patch.object(daily, "WEEKLY_REFRESH_LOCK_WAIT_SECONDS", 0):
                self.assertIsNone(daily.acquire_week_cache_lock(start))
            path.read_text.return_value = first[1]
            daily.release_week_cache_lock(start, first)
        path.unlink.assert_called_once()

    def test_competition_request_uses_scoped_endpoint_and_date_filters(self):
        response = type("Response", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
            "read": lambda self, *args: b'{"matches": []}',
        })()
        with patch.object(daily.urllib.request, "urlopen", return_value=response) as open_request:
            self.assertEqual(
                daily.fetch_football_data_competition_fixtures(
                    "PL", "2026-11-09", "2026-11-16", "secret-token"
                ),
                [],
            )
        url = open_request.call_args.args[0].full_url
        self.assertIn("/competitions/PL/matches?", url)
        self.assertIn("dateFrom=2026-11-09", url)
        self.assertIn("dateTo=2026-11-16", url)
        self.assertNotIn("secret-token", url)
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

    def test_weekly_fixtures_merge_supported_competitions_and_turkish_dates(self):
        start = date(2026, 11, 10)
        early = sample_match(201, "2026-11-09T22:00:00Z")
        late = sample_match(202, "2026-11-16T20:59:00Z")
        outside = sample_match(203, "2026-11-16T21:00:00Z")
        european = sample_match(204, "2026-11-11T18:00:00Z")
        with patch.object(daily, "today_turkey", return_value=start), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(daily, "fetch_football_data_fixture_range", return_value=[early, late, outside]) as fetch, patch.object(daily, "fetch_football_data_competition_fixtures", side_effect=[[european], [], [], [], [], []]) as competition_fetch, patch.object(daily, "save_week_cache", side_effect=lambda value, matches, diagnostics: {"start_date": value.isoformat(), "matches": matches, "diagnostics": diagnostics}):
            result = daily.get_weekly_fixtures(start, force_refresh=True)
        fetch.assert_called_once_with(date(2026, 11, 9), date(2026, 11, 16), "test")
        self.assertEqual(competition_fetch.call_count, 6)
        self.assertEqual([item["match_id"] for item in result["matches"]], ["201", "204", "202"])
        self.assertEqual(result["diagnostics"]["provider_match_count"], 3)
        self.assertEqual(result["diagnostics"]["filtered_match_count"], 3)
        self.assertEqual(result["diagnostics"]["competition_success_count"], 6)

    def test_competition_http_error_is_not_reported_as_zero_matches(self):
        start = date(2026, 11, 10)
        with patch.object(daily, "today_turkey", return_value=start), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(daily, "fetch_football_data_fixture_range", return_value=[]), patch.object(daily, "fetch_football_data_competition_fixtures", side_effect=[daily.DailyFixtureError("football-data HTTP status: 403"), [], [], [], [], []]), patch.object(daily, "save_week_cache", side_effect=lambda value, matches, diagnostics: {"matches": matches, "diagnostics": diagnostics}):
            result = daily.get_weekly_fixtures(start, force_refresh=True)
        first = result["diagnostics"]["competition_requests"][0]
        self.assertEqual(first["competition"], "PL")
        self.assertEqual(first["status"], "error")
        self.assertEqual(first["http_status"], "403")
        self.assertIsNone(first["provider_match_count"])

    def test_week_cache_avoids_range_request(self):
        start = date(2026, 11, 10)
        cached = {"start_date": start.isoformat(), "matches": []}
        with patch.object(daily, "today_turkey", return_value=start), patch.object(daily, "load_week_cache", return_value=cached), patch.object(daily, "fetch_football_data_fixture_range", side_effect=AssertionError("network must not be called")):
            self.assertEqual(daily.get_weekly_fixtures(start), cached)

    def test_worker_waiting_for_refresh_reads_new_cache_without_api_call(self):
        start = date(2026, 11, 10)
        cached = {"start_date": start.isoformat(), "matches": []}
        with patch.object(daily, "today_turkey", return_value=start), patch.object(daily, "load_week_cache", side_effect=[None, cached]), patch.object(daily, "acquire_week_cache_lock", return_value=None), patch.object(daily, "fetch_football_data_fixture_range", side_effect=AssertionError("network must not be called")):
            self.assertEqual(daily.get_weekly_fixtures(start), cached)

    def test_worker_does_not_duplicate_refresh_when_lock_is_busy(self):
        start = date(2026, 11, 10)
        with patch.object(daily, "today_turkey", return_value=start), patch.object(daily, "load_week_cache", return_value=None), patch.object(daily, "acquire_week_cache_lock", return_value=None), patch.object(daily, "fetch_football_data_fixture_range", side_effect=AssertionError("network must not be called")):
            with self.assertRaisesRegex(daily.DailyFixtureError, "refresh is already in progress"):
                daily.get_weekly_fixtures(start)

    def test_partial_429_and_timeout_are_diagnostics_not_zero_matches(self):
        start = date(2026, 11, 10)
        failures = [
            daily.DailyFixtureError("football-data HTTP status: 429"),
            daily.DailyFixtureError("football-data request failed"),
            [], [], [], [],
        ]
        with patch.object(daily, "today_turkey", return_value=start), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(daily, "load_week_cache", return_value=None), patch.object(daily, "acquire_week_cache_lock", return_value=(1, "test-lock")), patch.object(daily, "release_week_cache_lock"), patch.object(daily, "fetch_football_data_fixture_range", return_value=[]), patch.object(daily, "fetch_football_data_competition_fixtures", side_effect=failures), patch.object(daily, "save_week_cache", side_effect=lambda value, matches, diagnostics: {"matches": matches, "diagnostics": diagnostics}):
            result = daily.get_weekly_fixtures(start, force_refresh=True)
        reports = result["diagnostics"]["competition_requests"]
        self.assertEqual(reports[0]["http_status"], "429")
        self.assertEqual(reports[1]["http_status"], "request_failed")
        self.assertIsNone(reports[0]["provider_match_count"])

    def test_weekly_diagnostics_never_log_api_key(self):
        start = date(2026, 11, 10)
        secret = "not-a-real-key"
        with patch.object(daily, "today_turkey", return_value=start), patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": secret}), patch.object(daily, "fetch_football_data_fixture_range", return_value=[]), patch.object(daily, "fetch_football_data_competition_fixtures", return_value=[]), patch.object(daily, "save_week_cache", side_effect=lambda value, matches, diagnostics: {"matches": matches, "diagnostics": diagnostics}), self.assertLogs(daily.LOGGER, level="INFO") as logs:
            daily.get_weekly_fixtures(start, force_refresh=True)
        self.assertNotIn(secret, "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
