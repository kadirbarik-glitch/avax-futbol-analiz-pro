
"""AVAX V8.4 - Analysis Bridge Safety Tests.

Offline tests only.
No API calls, predictions, or deployment.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from v84_analysis_bridge import (
    check_analysis_eligibility,
    prepare_analysis,
)


NOW = datetime.fromisoformat(
    "2026-11-11T12:00:00+03:00"
)


def sample_match(**changes):
    match = {
        "match_id": "12345",
        "league_id": 203,
        "home_team_id": "10",
        "away_team_id": "20",
        "kickoff_tr": "2026-11-11T18:00:00+03:00",
        "status": "NS",
    }
    match.update(changes)
    return match


class AnalysisBridgeTests(unittest.TestCase):

    def test_future_match_passes_basic_checks(self):
        result = check_analysis_eligibility(
            sample_match(), NOW
        )
        self.assertTrue(result["eligible"])
        self.assertFalse(result["analysis_ready"])

    def test_past_match_blocked(self):
        result = check_analysis_eligibility(
            sample_match(
                kickoff_tr="2026-11-11T10:00:00+03:00"
            ),
            NOW,
        )
        self.assertFalse(result["eligible"])

    def test_live_match_blocked(self):
        result = check_analysis_eligibility(
            sample_match(status="1H"), NOW
        )
        self.assertFalse(result["eligible"])

    def test_finished_match_blocked(self):
        result = check_analysis_eligibility(
            sample_match(status="FT"), NOW
        )
        self.assertFalse(result["eligible"])

    def test_postponed_match_blocked(self):
        result = check_analysis_eligibility(
            sample_match(status="PST"), NOW
        )
        self.assertFalse(result["eligible"])

    def test_missing_team_blocked(self):
        result = check_analysis_eligibility(
            sample_match(home_team_id=None), NOW
        )
        self.assertFalse(result["eligible"])

    def test_identical_teams_blocked(self):
        result = check_analysis_eligibility(
            sample_match(away_team_id="10"), NOW
        )
        self.assertFalse(result["eligible"])

    def test_invalid_kickoff_blocked(self):
        result = check_analysis_eligibility(
            sample_match(kickoff_tr="invalid"), NOW
        )
        self.assertFalse(result["eligible"])

    def test_invalid_match_data_blocked(self):
        result = check_analysis_eligibility(
            None, NOW
        )
        self.assertFalse(result["eligible"])

    def test_no_prediction_before_integration(self):
        result = prepare_analysis(
            sample_match(), NOW
        )
        self.assertIsNone(result["prediction"])
        self.assertFalse(result["analysis_ready"])

    def test_same_provider_fixture_uses_existing_prediction_engine(self):
        match = sample_match(provider="football-data.org", league_id="PL")
        fake_prediction = {"probabilities_percent": {"home": 50}}
        with patch("v8_data.analyze_match", return_value=fake_prediction) as analyze:
            result = prepare_analysis(match, NOW)
        self.assertTrue(result["analysis_ready"])
        self.assertEqual(result["prediction"], fake_prediction)
        analyze.assert_called_once_with("PL", 10, 20, match["kickoff_tr"])

    def test_unsupported_same_provider_competition_is_blocked(self):
        result = check_analysis_eligibility(
            sample_match(provider="football-data.org", league_id="TR1"), NOW
        )
        self.assertFalse(result["eligible"])


if __name__ == "__main__":
    unittest.main()
