"""Offline tests for the separate V8.4 mobile beta server."""

import os
import unittest
from datetime import date
from unittest.mock import patch

import app_v84_beta as beta


def fixture():
    return {
        "provider": "football-data.org", "match_id": "44", "league_id": "PL",
        "league": "Premier League", "country": "England", "home_team_id": "1",
        "home_team": "Home", "away_team_id": "2", "away_team": "Away",
        "date_tr": "2026-11-10", "kickoff_tr": "2026-11-11T20:00:00+03:00", "status": "SCHEDULED",
    }


class BetaAppTests(unittest.TestCase):
    def setUp(self):
        self.client = beta.app.test_client()
        self.today = patch.object(beta, "today_turkey", return_value=date(2026, 11, 10))
        self.today.start()
        self.addCleanup(self.today.stop)

    def auth(self):
        return {"Authorization": "Basic YmV0YTpwYXNz"}

    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"Home", response.data)

    def test_invalid_credentials_are_challenged(self):
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True):
            response = self.client.get("/", headers={"Authorization": "Basic YmFkOmNyZWRz"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic", response.headers["WWW-Authenticate"])

    def test_authenticated_mobile_list_uses_fixture_data(self):
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True), patch.object(beta, "get_weekly_fixtures", return_value={"matches": [fixture()]}), patch.object(beta, "kickoff_is_past", return_value=False):
            response = self.client.get("/?date=2026-11-10", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Home", response.data)
        self.assertIn(b"Detay ve analiz", response.data)
        self.assertIn("Analiz destekleniyor".encode("utf-8"), response.data)

    def test_unsupported_league_is_explicitly_labelled(self):
        unsupported = fixture()
        unsupported["league_id"] = "BSA"
        unsupported["league"] = "Brazilian Serie A"
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True), patch.object(beta, "get_weekly_fixtures", return_value={"matches": [unsupported]}), patch.object(beta, "kickoff_is_past", return_value=False):
            response = self.client.get("/?date=2026-11-10", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Analiz desteklenmiyor".encode("utf-8"), response.data)

    def test_supported_leagues_are_prioritized_within_a_match_group(self):
        unsupported = fixture()
        unsupported.update({"match_id": "45", "league_id": "BSA", "kickoff_tr": "2027-11-11T18:00:00+03:00"})
        supported = fixture()
        supported.update({"match_id": "46", "kickoff_tr": "2027-11-11T20:00:00+03:00"})
        groups = beta.match_groups([unsupported, supported])
        self.assertEqual([row["match_id"] for row in groups["upcoming"]], ["46", "45"])

    def test_calendar_has_seven_days_and_marks_real_match_count(self):
        match = fixture()
        match["date_tr"] = "2026-11-12"
        calendar = beta.weekly_calendar(date(2026, 11, 10), [match])
        self.assertEqual(len(calendar), 7)
        self.assertEqual(calendar[2]["count"], 1)
        self.assertEqual(calendar[0]["count"], 0)

    def test_home_rejects_date_outside_seven_day_calendar(self):
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True):
            response = self.client.get("/?date=2026-11-17", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertIn("7 günü gösterir".encode("utf-8"), response.data)

    def test_detail_never_invents_prediction_when_bridge_blocks(self):
        blocked = {"prediction": None, "reason": "Match is not upcoming", "warning": "No prediction has been generated."}
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True), patch.object(beta, "get_daily_fixtures", return_value={"matches": [fixture()]}), patch.object(beta, "prepare_analysis", return_value=blocked):
            response = self.client.get("/match/44?date=2026-11-10", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match is not upcoming", response.data)
        self.assertNotIn(b"%50", response.data)

    def test_detail_displays_real_bridge_probability(self):
        ready = {"prediction": {"probabilities_percent": {"home": 52, "draw": 25}, "market_data_quality": {"match_result": {"level": "ADEQUATE", "freshness": "FRESH"}}}, "warning": "Informational output."}
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True), patch.object(beta, "get_daily_fixtures", return_value={"matches": [fixture()]}), patch.object(beta, "prepare_analysis", return_value=ready):
            response = self.client.get("/match/44?date=2026-11-10", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ev sahibi".encode("utf-8"), response.data)
        self.assertIn(b"%52", response.data)

    def test_low_quality_prediction_is_not_displayed(self):
        low_quality = {"prediction": {"probabilities_percent": {"home": 99}, "market_data_quality": {"match_result": {"level": "LOW", "freshness": "FRESH"}}}, "warning": "Informational output."}
        with patch.dict(os.environ, {"BETA_USERNAME": "beta", "BETA_PASSWORD": "pass"}, clear=True), patch.object(beta, "get_daily_fixtures", return_value={"matches": [fixture()]}), patch.object(beta, "prepare_analysis", return_value=low_quality):
            response = self.client.get("/match/44?date=2026-11-10", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertIn("olasılık gösterilmez".encode("utf-8"), response.data)
        self.assertNotIn(b"%99", response.data)

    def test_healthz_does_not_require_credentials_or_expose_data(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "service": "avax-v84-beta"})


if __name__ == "__main__":
    unittest.main()
