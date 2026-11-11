
"""AVAX V8.4 - Mapping Verifier Safety Tests.

18 offline tests.
No API requests, real predictions or deployment.
"""

import unittest

from v84_mapping_verifier import (
    TeamIdentity,
    MappingCandidate,
    VerificationError,
    normalize_name,
    validate_identity,
    similarity_score,
    compare_teams,
    find_candidates,
    verification_report,
    can_activate_mapping,
)


def source_team(**changes):
    data = {
        "provider": "api-football",
        "team_id": 42,
        "name": "Arsenal",
        "country": "England",
        "league": "Premier League",
    }
    data.update(changes)
    return TeamIdentity(**data)


def target_team(**changes):
    data = {
        "provider": "football-data",
        "team_id": 57,
        "name": "Arsenal FC",
        "country": "England",
        "league": "Premier League",
    }
    data.update(changes)
    return TeamIdentity(**data)


class MappingVerifierTests(unittest.TestCase):

    def test_normalize_name(self):
        self.assertEqual(
            normalize_name("  ARSENAL FC  "),
            "arsenal fc",
        )

    def test_normalize_invalid_name(self):
        self.assertEqual(normalize_name(None), "")

    def test_valid_source_identity(self):
        team = source_team()
        self.assertEqual(validate_identity(team), team)

    def test_invalid_identity_type(self):
        with self.assertRaises(VerificationError):
            validate_identity(None)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(VerificationError):
            validate_identity(
                source_team(provider="unknown")
            )

    def test_zero_team_id_rejected(self):
        with self.assertRaises(VerificationError):
            validate_identity(
                source_team(team_id=0)
            )

    def test_boolean_team_id_rejected(self):
        with self.assertRaises(VerificationError):
            validate_identity(
                source_team(team_id=True)
            )

    def test_missing_team_name_rejected(self):
        with self.assertRaises(VerificationError):
            validate_identity(
                source_team(name="")
            )

    def test_identical_name_similarity(self):
        score = similarity_score(
            source_team(),
            target_team(name="Arsenal"),
        )
        self.assertEqual(score, 1.0)

    def test_valid_candidate_pending(self):
        candidate = compare_teams(
            source_team(),
            target_team(),
        )
        self.assertEqual(candidate.status, "PENDING")
        self.assertGreater(candidate.similarity, 0)

    def test_wrong_source_provider_rejected(self):
        with self.assertRaises(VerificationError):
            compare_teams(
                source_team(provider="football-data"),
                target_team(),
            )

    def test_country_mismatch_rejected(self):
        with self.assertRaises(VerificationError):
            compare_teams(
                source_team(),
                target_team(country="Spain"),
            )

    def test_league_mismatch_rejected(self):
        with self.assertRaises(VerificationError):
            compare_teams(
                source_team(),
                target_team(league="La Liga"),
            )

    def test_find_candidates(self):
        candidates = find_candidates(
            source_team(),
            [
                target_team(),
                target_team(
                    team_id=99,
                    name="Chelsea",
                ),
            ],
            minimum_similarity=0.60,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].target.team_id, 57
        )

    def test_invalid_similarity_threshold(self):
        with self.assertRaises(VerificationError):
            find_candidates(
                source_team(),
                [],
                minimum_similarity=1.5,
            )

    def test_report_requires_manual_review(self):
        candidate = compare_teams(
            source_team(),
            target_team(),
        )
        report = verification_report(candidate)

        self.assertEqual(report["status"], "PENDING")
        self.assertFalse(report["verified"])
        self.assertTrue(
            report["requires_manual_review"]
        )

    def test_approved_candidate_report_rejected(self):
        candidate = MappingCandidate(
            source=source_team(),
            target=target_team(),
            similarity=1.0,
            status="APPROVED",
        )
        with self.assertRaises(VerificationError):
            verification_report(candidate)

    def test_mapping_never_auto_activates(self):
        candidate = compare_teams(
            source_team(),
            target_team(),
        )
        report = verification_report(candidate)

        self.assertFalse(
            can_activate_mapping(report)
        )
        self.assertFalse(
            can_activate_mapping(None)
        )


if __name__ == "__main__":
    unittest.main()
