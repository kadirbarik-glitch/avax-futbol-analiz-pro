
"""AVAX V8.4 - Provider Identity Check Tests.

Offline tests only.
No real API requests, predictions or deployment.
"""

import os
import unittest
from unittest.mock import patch

from v84_provider_identity_check import (
    ProviderIdentityError,
    fetch_api_football_teams,
    fetch_football_data_teams,
    build_identity_report,
)


def api_football_response():
    return {
        "errors": [],
        "response": [
            {
                "team": {
                    "id": 42,
                    "name": "Arsenal",
                }
            },
            {
                "team": {
                    "id": 49,
                    "name": "Chelsea",
                }
            },
        ],
    }


def football_data_response():
    return {
        "teams": [
            {
                "id": 57,
                "name": "Arsenal FC",
            },
            {
                "id": 61,
                "name": "Chelsea FC",
            },
        ],
    }


class ProviderIdentityCheckTests(unittest.TestCase):

    def setUp(self):
        self.env_patch = patch.dict(
            os.environ,
            {
                "API_FOOTBALL_KEY": "test-key",
                "FOOTBALL_DATA_API_KEY": "test-key",
            },
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_api_football_teams_parsed(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            return_value=api_football_response(),
        ):
            teams = fetch_api_football_teams(2026)

        self.assertEqual(len(teams), 2)
        self.assertEqual(teams[0].team_id, 42)
        self.assertEqual(teams[0].name, "Arsenal")

    def test_football_data_teams_parsed(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            return_value=football_data_response(),
        ):
            teams = fetch_football_data_teams()

        self.assertEqual(len(teams), 2)
        self.assertEqual(teams[0].team_id, 57)

    def test_missing_api_football_key(self):
        with patch.dict(
            os.environ,
            {"API_FOOTBALL_KEY": ""},
        ):
            with self.assertRaises(
                ProviderIdentityError
            ):
                fetch_api_football_teams(2026)

    def test_missing_football_data_key(self):
        with patch.dict(
            os.environ,
            {"FOOTBALL_DATA_API_KEY": ""},
        ):
            with self.assertRaises(
                ProviderIdentityError
            ):
                fetch_football_data_teams()

    def test_invalid_season_rejected(self):
        with self.assertRaises(
            ProviderIdentityError
        ):
            fetch_api_football_teams(2010)

    def test_boolean_season_rejected(self):
        with self.assertRaises(
            ProviderIdentityError
        ):
            fetch_api_football_teams(True)

    def test_invalid_api_response_rejected(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            return_value={"response": None},
        ):
            with self.assertRaises(
                ProviderIdentityError
            ):
                fetch_api_football_teams(2026)

    def test_api_error_response_rejected(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            return_value={
                "errors": {"token": "invalid"},
                "response": [],
            },
        ):
            with self.assertRaises(
                ProviderIdentityError
            ):
                fetch_api_football_teams(2026)

    def test_invalid_football_data_response(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            return_value={"teams": None},
        ):
            with self.assertRaises(
                ProviderIdentityError
            ):
                fetch_football_data_teams()

    def test_invalid_team_skipped(self):
        payload = {
            "errors": [],
            "response": [
                {"team": {"id": 42, "name": "Arsenal"}},
                {"team": {"id": None, "name": "Bad"}},
            ],
        }

        with patch(
            "v84_provider_identity_check.fetch_json",
            return_value=payload,
        ):
            teams = fetch_api_football_teams(2026)

        self.assertEqual(len(teams), 1)

    def test_report_has_pending_candidates(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            side_effect=[
                api_football_response(),
                football_data_response(),
            ],
        ):
            report = build_identity_report(2026)

        self.assertEqual(report["source_count"], 2)
        self.assertEqual(report["target_count"], 2)
        self.assertEqual(report["verified_mappings"], 0)
        self.assertFalse(report["auto_activated"])

        self.assertTrue(
            report["results"][0]["candidates"]
        )

        self.assertEqual(
            report["results"][0]["candidates"][0]["status"],
            "PENDING",
        )

    def test_report_never_auto_verifies(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            side_effect=[
                api_football_response(),
                football_data_response(),
            ],
        ):
            report = build_identity_report(2026)

        for item in report["results"]:
            for candidate in item["candidates"]:
                self.assertFalse(candidate["verified"])
                self.assertTrue(
                    candidate["requires_manual_review"]
                )

    def test_report_with_no_matches(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            side_effect=[
                api_football_response(),
                {"teams": []},
            ],
        ):
            report = build_identity_report(2026)

        self.assertEqual(report["target_count"], 0)

        for item in report["results"]:
            self.assertEqual(item["candidates"], [])

    def test_invalid_threshold_rejected(self):
        with patch(
            "v84_provider_identity_check.fetch_json",
            side_effect=[
                api_football_response(),
                football_data_response(),
            ],
        ):
            with self.assertRaises(ValueError):
                build_identity_report(
                    2026,
                    minimum_similarity=1.5,
                )


if __name__ == "__main__":
    unittest.main()
