"""Offline tests for dynamic league discovery and eligibility."""

import unittest

from v8_leagues import discover_catalog, selected_capability


class LeagueCatalogTests(unittest.TestCase):

    def test_turkey_is_prioritized_without_model_fallback(self):
        catalog = discover_catalog({
            "competitions": [
                {
                    "code": "PL",
                    "name": "Premier League",
                    "area": {"name": "England", "code": "ENG"},
                },
                {
                    "code": "TSL",
                    "name": "Süper Lig",
                    "area": {"name": "Turkey", "code": "TUR"},
                },
            ]
        })

        self.assertEqual(catalog[0]["code"], "TSL")
        self.assertEqual(catalog[0]["access_status"], "ACCESSIBLE")
        self.assertEqual(catalog[0]["model_status"], "RESEARCH_REQUIRED")
        self.assertFalse(catalog[0]["prediction_allowed"])
        self.assertTrue(catalog[1]["prediction_allowed"])

    def test_catalog_error_disables_prediction(self):
        catalog = discover_catalog(None, "Katalog kullanilamiyor")

        self.assertEqual(len(catalog), 6)
        self.assertTrue(all(
            entry["access_status"] == "CATALOG_UNAVAILABLE"
            and not entry["prediction_allowed"]
            for entry in catalog
        ))

    def test_unknown_league_is_not_accessible(self):
        capability = selected_capability([], "TSL")

        self.assertEqual(capability["access_status"], "NOT_ACCESSIBLE")
        self.assertFalse(capability["prediction_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
