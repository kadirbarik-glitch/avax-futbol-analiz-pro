"""Offline chronology and calibration tests; no provider calls."""

import unittest
import json
from pathlib import Path

import backtest_v85_calibration as calibration


def row(probability, outcome):
    return {"prediction": {"btts": probability, "over25": probability}, "baseline": {"btts": .5, "over25": .5}, "outcome": {"btts": outcome, "over25": outcome}}


class V85CalibrationTests(unittest.TestCase):
    def test_platt_uses_training_rows_not_validation_outcomes(self):
        train = [row(.8, 1) for _ in range(30)]
        model = calibration.fit_platt(train, "btts", iterations=20)
        before = calibration.apply(model, .8)
        validation = [row(.8, 0) for _ in range(30)]
        self.assertEqual(before, calibration.apply(model, .8))
        self.assertEqual(calibration.evaluate(validation, "btts", model)["calibrated"]["n"], 30)

    def test_isotonic_is_monotonic(self):
        rows = [row(.2, 0) for _ in range(30)] + [row(.8, 1) for _ in range(30)]
        model = calibration.fit_isotonic(rows, "over25")
        self.assertLessEqual(calibration.apply(model, .2), calibration.apply(model, .8))

    def test_empty_scores_do_not_fabricate_metrics(self):
        self.assertEqual(calibration.scores([], "btts", []), {"n": 0, "brier": None, "log_loss": None, "ece": None})

    def test_manifest_preserves_chronological_protocol(self):
        manifest = json.loads(Path("v85_calibration_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["protocol"]["train"], "2023")
        self.assertEqual(manifest["protocol"]["validation"], "2024")
        self.assertEqual(manifest["protocol"]["exploratory"], "2025")
        self.assertFalse(manifest["protocol"]["random_split"])
        self.assertFalse(manifest["live_model_changed"])


if __name__ == "__main__":
    unittest.main()
