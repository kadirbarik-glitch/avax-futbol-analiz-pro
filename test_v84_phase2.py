"""Offline checks for paired uncertainty and quality slices."""

import unittest

import backtest_v84_phase2 as phase2


def row(prediction, baseline, outcome, quality="ADEQUATE"):
    return {"prediction": prediction, "baseline": baseline, "outcome": outcome, "quality": quality}


class Phase2Tests(unittest.TestCase):
    def test_paired_bootstrap_preserves_fixture_pairing(self):
        values = [-.1, -.1, -.1, -.1]
        result = phase2.bootstrap_interval(values, samples=100, seed=1)
        self.assertEqual(result["mean_delta"], -.1)
        self.assertEqual(result["ci95_low"], -.1)
        self.assertEqual(result["ci95_high"], -.1)

    def test_high_probability_reports_sample_size_and_observed_rate(self):
        rows = [row({"home": .8, "draw": .1, "away": .1, "over25": .8, "btts": .2}, {"home": .4, "draw": .3, "away": .3, "over25": .5, "btts": .5}, {"home": 1, "draw": 0, "away": 0, "over25": 1, "btts": 0})]
        result = phase2.high_probability(rows, ("over25",))
        self.assertEqual(result["n"], 1)
        self.assertEqual(result["observed_rate"], 1)

    def test_empty_quality_slice_has_no_fabricated_metrics(self):
        report = phase2.market_report([], ("btts",), 1)
        self.assertEqual(report["n"], 0)
        self.assertIsNone(report["v8_brier"])
        self.assertIsNone(report["paired_brier_delta"])


if __name__ == "__main__":
    unittest.main()
