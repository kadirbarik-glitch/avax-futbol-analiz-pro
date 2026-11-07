"""Offline route and data-coverage tests for dynamic competitions."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import app_v8
import app_v3
import v8_data


def fixture(index, date):
    return {
        "id": index,
        "utcDate": date,
        "status": "FINISHED",
        "homeTeam": {"id": 1},
        "awayTeam": {"id": 2},
        "score": {"fullTime": {"home": 1, "away": 0}},
    }


class DynamicLeagueTests(unittest.TestCase):

    def test_catalog_uses_long_ttl(self):
        with patch.object(
            app_v8, "api_get", return_value=({}, None)
        ) as api:
            app_v8.get_leagues()

        api.assert_called_once_with(
            "/competitions", cache_seconds=43200
        )

    def test_catalog_cache_avoids_repeat_network_request(self):
        with patch.dict(
            app_v3.API_CACHE,
            {"/competitions": {
                "data": {"competitions": []},
                "time": 100,
            }},
            clear=True,
        ), patch.object(
            app_v3.time, "monotonic", return_value=101
        ), patch.object(app_v3, "urlopen") as request:
            data, error = app_v3.api_get(
                "/competitions", cache_seconds=43200
            )

        self.assertEqual(data, {"competitions": []})
        self.assertIsNone(error)
        request.assert_not_called()

    def test_unvalidated_league_cannot_post_prediction(self):
        catalog = [{
            "code": "TSL",
            "name": "Süper Lig",
            "area": "Turkey",
            "turkey_priority": True,
            "access_status": "ACCESSIBLE",
            "access_message": "Erisilebilir.",
            "model_status": "RESEARCH_REQUIRED",
            "model_message": "Model dogrulamasi gerekli.",
            "data_status": "NOT_CHECKED",
            "data_message": "Kontrol bekliyor.",
            "prediction_allowed": False,
        }]

        with patch.object(
            app_v8, "get_leagues", return_value=catalog
        ), patch.object(
            app_v8, "api_get",
            return_value=({"matches": []}, None),
        ), patch.object(
            app_v8, "competition_readiness",
            return_value={
                "status": "SUFFICIENT_FOR_RESEARCH",
                "message": "Arastirma verisi yeterli.",
                "matches": 20,
            },
        ), patch.object(app_v8, "analyze_match") as analyze:
            response = app_v8.app.test_client().post(
                "/v8", data={"league": "TSL", "match_id": "1"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Bu lig icin tahmin uretilemez", response.data
        )
        analyze.assert_not_called()

    def test_research_readiness_reports_coverage_without_model(self):
        kickoff = datetime.now(timezone.utc) + timedelta(days=1)
        matches = [
            fixture(
                index,
                (kickoff - timedelta(days=index + 1)).isoformat(),
            )
            for index in range(20)
        ]

        with patch.object(
            v8_data, "api_get",
            return_value=({"matches": matches}, None),
        ):
            readiness = v8_data.competition_readiness(
                "TSL", kickoff.isoformat()
            )

        self.assertEqual(
            readiness["status"], "SUFFICIENT_FOR_RESEARCH"
        )
        self.assertEqual(readiness["matches"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
