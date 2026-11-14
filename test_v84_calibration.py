"""Offline leakage and metric tests for chronological V8 calibration."""

import unittest

import backtest_v84_calibration as calibration


def match(mid, kickoff, home, away, home_goals=1, away_goals=0):
    return {
        "id": mid, "utcDate": kickoff, "status": "FINISHED",
        "homeTeam": {"id": home}, "awayTeam": {"id": away},
        "score": {"fullTime": {"home": home_goals, "away": away_goals}},
    }


def prediction(*_args):
    return {"probabilities_percent": {"home": 50, "draw": 25, "away": 25, "over25": 50, "btts": 50}}


class CalibrationTests(unittest.TestCase):

    def test_same_kickoff_batch_never_enters_its_own_history(self):
        matches = [
            match(1, "2025-01-01T12:00:00Z", 1, 2),
            match(2, "2025-01-02T12:00:00Z", 1, 2),
            match(3, "2025-01-03T12:00:00Z", 1, 2),
            match(4, "2025-01-04T12:00:00Z", 1, 2),
            match(5, "2025-01-05T12:00:00Z", 1, 2),
            match(6, "2025-01-06T12:00:00Z", 1, 2),
            match(7, "2025-01-07T12:00:00Z", 1, 2),
        ]
        seen = []

        def guarded_predict(_league, _home, _away, kickoff, history):
            self.assertTrue(all(item["utcDate"] < kickoff for item in history))
            seen.append((kickoff, {item["id"] for item in history}))
            return prediction()

        rows = calibration.chronological_rows("PL", matches, guarded_predict)
        self.assertEqual([row["id"] for row in rows], [4, 5, 6, 7])
        self.assertNotIn(7, seen[-1][1])

    def test_metrics_and_calibration_keep_market_samples_separate(self):
        rows = [{"quality": "LOW", "prediction": {"home": .6, "draw": .2, "away": .2, "over25": .7, "btts": .4}, "baseline": {"home": .4, "draw": .3, "away": .3, "over25": .5, "btts": .5}, "outcome": {"home": 1, "draw": 0, "away": 0, "over25": 1, "btts": 0}}]
        report = calibration.report_rows(rows)
        self.assertEqual(report["sample_size"], 1)
        self.assertEqual(report["quality"], {"LOW": 1})
        self.assertAlmostEqual(report["markets"]["over25"]["v8_brier"], .09)
        self.assertEqual(report["markets"]["match_result"]["calibration"]["home"][0]["n"], 1)

    def test_insufficient_fixtures_are_reported_not_scored(self):
        matches = [match(1, "2025-01-01T12:00:00Z", 1, 2)]
        quality = calibration.pre_kickoff_quality_counts(matches)
        report = calibration.report_rows([], quality)
        self.assertEqual(quality, {"INSUFFICIENT": 1})
        self.assertEqual(report["sample_size"], 0)
        self.assertEqual(report["insufficient_excluded"], 1)

    def test_duplicate_ids_are_rejected_before_evaluation(self):
        duplicate = [match(1, "2025-01-01T12:00:00Z", 1, 2), match(1, "2025-01-02T12:00:00Z", 1, 2)]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            calibration.ordered_matches(duplicate)


if __name__ == "__main__":
    unittest.main()
