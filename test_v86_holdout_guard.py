"""Offline guards for a future independent 2026 evaluation."""

import unittest

import v86_holdout_guard as guard


def fixture(match_id=1, kickoff="2026-05-01T18:00:00Z", status="FINISHED"):
    return {"id": match_id, "utcDate": kickoff, "status": status, "homeTeam": {"id": 1}, "awayTeam": {"id": 2}, "score": {"fullTime": {"home": 1, "away": 0}}}


class HoldoutGuardTests(unittest.TestCase):
    def test_frozen_manifest_matches_current_selections(self):
        manifest = guard.verify_manifest()
        self.assertFalse(manifest["allow_model_selection"])

    def test_rejects_non_finished_future_and_duplicate_fixtures(self):
        with self.assertRaisesRegex(ValueError, "non-finished"):
            guard.validate_holdout_rows([fixture(status="SCHEDULED")], "2026-11-14T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "future"):
            guard.validate_holdout_rows([fixture(kickoff="2026-12-01T18:00:00Z")], "2026-11-14T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            guard.validate_holdout_rows([fixture(), fixture()], "2026-11-14T00:00:00Z")

    def test_returns_chronological_order_only_after_validation(self):
        rows = guard.validate_holdout_rows([fixture(2, "2026-05-02T18:00:00Z"), fixture(1, "2026-05-01T18:00:00Z")], "2026-11-14T00:00:00Z")
        self.assertEqual([row["id"] for row in rows], [1, 2])


if __name__ == "__main__":
    unittest.main()
