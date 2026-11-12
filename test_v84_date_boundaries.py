"""UTC-to-Turkey boundaries for football-data.org fixtures."""

import unittest

import v84_daily_fixtures as daily


def match(match_id, utc_date):
    return {
        "id": match_id, "utcDate": utc_date, "status": "SCHEDULED",
        "competition": {"code": "PL", "name": "Premier League", "area": {"name": "England"}},
        "homeTeam": {"id": 10, "name": "Home"},
        "awayTeam": {"id": 20, "name": "Away"},
    }


class TurkeyDateBoundaryTests(unittest.TestCase):
    def test_turkish_midnight_begins_at_previous_utc_2100(self):
        result = daily.normalize_daily_fixture(match(1, "2026-11-09T21:00:00Z"))
        self.assertEqual(result["date_tr"], "2026-11-10")
        self.assertEqual(result["kickoff_tr"], "2026-11-10T00:00:00+03:00")

    def test_last_minute_of_turkish_day_stays_selected(self):
        result = daily.normalize_daily_fixture(match(2, "2026-11-10T20:59:00Z"))
        self.assertEqual(result["date_tr"], "2026-11-10")

    def test_next_utc_minute_moves_to_next_turkish_day(self):
        result = daily.normalize_daily_fixture(match(3, "2026-11-10T21:00:00Z"))
        self.assertEqual(result["date_tr"], "2026-11-11")


if __name__ == "__main__":
    unittest.main()
