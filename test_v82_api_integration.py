
"""AVAX V8.2 - API integration safety tests.

Run:
python -m unittest -v test_v82_api_integration

Uses mocked API responses.
No network connection or API key required.
"""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import v8_data
from v8_models import MODEL_SELECTIONS


def fixture(mid, date, home, away, hg, ag,
            status="FINISHED"):
    return {
        "id": mid,
        "utcDate": date,
        "status": status,
        "homeTeam": {"id": home},
        "awayTeam": {"id": away},
        "score": {
            "fullTime": {
                "home": hg,
                "away": ag,
            }
        },
    }


def sample_matches():
    matches = []

    for day in range(1, 13):
        date = f"2025-09-{day:02d}T20:00:00Z"

        matches.extend([
            fixture(
                day * 10 + 1, date,
                1, 2,
                day % 4, (day + 1) % 3,
            ),
            fixture(
                day * 10 + 2, date,
                3, 4,
                (day + 2) % 4, day % 3,
            ),
        ])

    return matches


class APIIntegrationTests(unittest.TestCase):

    def test_six_competitions_supported(self):
        self.assertEqual(
            set(MODEL_SELECTIONS),
            {"PL", "PD", "SA", "BL1", "FL1", "CL"},
        )

    def test_champions_league_api_path(self):
        matches = sample_matches()

        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": matches}, None),
        ) as mocked:
            result = v8_data.league_history(
                "CL", "2025-10-01T20:00:00Z"
            )

        mocked.assert_called_once_with(
            "/competitions/CL/matches"
            "?season=2025&status=FINISHED"
        )
        self.assertEqual(len(result), len(matches))

    def test_future_matches_excluded(self):
        matches = sample_matches()
        matches.append(
            fixture(
                999,
                "2025-10-02T20:00:00Z",
                1, 2, 9, 0,
            )
        )

        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": matches}, None),
        ):
            result = v8_data.league_history(
                "CL", "2025-10-01T20:00:00Z"
            )

        self.assertNotIn(
            999, [m["id"] for m in result]
        )

    def test_same_kickoff_excluded(self):
        matches = sample_matches()
        matches.append(
            fixture(
                998,
                "2025-10-01T20:00:00Z",
                1, 2, 9, 9,
            )
        )

        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": matches}, None),
        ):
            result = v8_data.league_history(
                "CL", "2025-10-01T20:00:00Z"
            )

        self.assertNotIn(
            998, [m["id"] for m in result]
        )

    def test_unfinished_matches_excluded(self):
        matches = sample_matches()
        matches.append(
            fixture(
                997,
                "2025-09-15T20:00:00Z",
                1, 2, 2, 1,
                status="SCHEDULED",
            )
        )

        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": matches}, None),
        ):
            result = v8_data.league_history(
                "CL", "2025-10-01T20:00:00Z"
            )

        self.assertNotIn(
            997, [m["id"] for m in result]
        )

    def test_api_error_rejected(self):
        with patch.object(
            v8_data, "api_get",
            return_value=(None, "API unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                v8_data.league_history(
                    "CL", "2025-10-01T20:00:00Z"
                )

    def test_invalid_api_response_rejected(self):
        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": None}, None),
        ):
            with self.assertRaises(RuntimeError):
                v8_data.league_history(
                    "CL", "2025-10-01T20:00:00Z"
                )

    def test_season_boundary(self):
        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": []}, None),
        ) as mocked:
            v8_data.league_history(
                "CL", "2026-03-01T20:00:00Z"
            )

        mocked.assert_called_once_with(
            "/competitions/CL/matches"
            "?season=2025&status=FINISHED"
        )

    def test_prediction_uses_filtered_history(self):
        matches = sample_matches()

        future = datetime.now(timezone.utc) + timedelta(
            days=30
        )
        kickoff = future.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        captured = {}

        def fake_predict(
            league, home_id, away_id,
            kickoff_value, history
        ):
            captured["history"] = copy.deepcopy(history)
            return {
                "league": league,
                "probabilities_percent": {},
            }

        with patch.object(
            v8_data, "league_history",
            return_value=matches,
        ), patch.object(
            v8_data, "predict",
            side_effect=fake_predict,
        ):
            result = v8_data.analyze_match(
                "CL", 1, 2, kickoff
            )

        self.assertEqual(result["league"], "CL")
        self.assertEqual(
            len(captured["history"]), len(matches)
        )
        self.assertFalse(result["live_odds_included"])

    def test_past_kickoff_rejected(self):
        with self.assertRaises(ValueError):
            v8_data.analyze_match(
                "CL", 1, 2,
                "2020-01-01T20:00:00Z"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
