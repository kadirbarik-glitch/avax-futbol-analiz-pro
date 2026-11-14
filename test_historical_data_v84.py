"""Offline tests for the resumable historical cache collector."""

import os
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import historical_data_v84 as collector


def fixture(mid=1):
    return {"id": mid, "utcDate": "2023-08-10T18:00:00Z", "status": "FINISHED", "homeTeam": {"id": 1}, "awayTeam": {"id": 2}, "score": {"fullTime": {"home": 1, "away": 0}}}


class HistoricalCollectorTests(unittest.TestCase):

    def test_existing_pl_cache_is_compatible_with_calibration(self):
        cached = collector.read_valid_cache("PL", "2023")
        self.assertIsNotNone(cached)
        self.assertGreater(len(cached), 0)

    def test_missing_key_never_opens_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(collector, "request_finished", side_effect=AssertionError("network")):
            result = collector.collect_one("PD", "2023", cache_dir=Path("not-used"))
        self.assertEqual(result["status"], "missing_api_key")

    def test_403_and_429_are_distinguished_without_writing(self):
        forbidden = urllib.error.HTTPError("https://example.invalid", 403, "forbidden", {}, None)
        limited = urllib.error.HTTPError("https://example.invalid", 429, "limited", {"Retry-After": "12"}, None)
        with patch.dict(os.environ, {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(collector, "request_finished", side_effect=forbidden), patch.object(collector, "atomic_save") as save:
            result = collector.collect_one("PD", "2023", cache_dir=Path("not-used"))
        self.assertEqual(result["status"], "forbidden")
        save.assert_not_called()
        with patch.dict(os.environ, {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(collector, "request_finished", side_effect=limited), patch.object(collector, "atomic_save") as save:
            result = collector.collect_one("PD", "2024", cache_dir=Path("not-used"))
        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(result["retry_after"], 12.0)
        save.assert_not_called()

    def test_finished_payload_is_saved_only_after_validation(self):
        with patch.dict(os.environ, {"FOOTBALL_DATA_API_KEY": "test"}), patch.object(collector, "request_finished", return_value=[fixture()]), patch.object(collector, "atomic_save") as save:
            result = collector.collect_one("PD", "2025", cache_dir=Path("not-used"))
        self.assertEqual(result["status"], "downloaded")
        self.assertEqual(result["matches"], 1)
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
