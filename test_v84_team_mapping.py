
"""AVAX V8.4 - Team Mapping Safety Tests.

Offline tests only.
No external API requests or deployment.
"""

import unittest
from unittest.mock import patch

from v84_team_mapping import (
    LeagueMapping,
    TeamMapping,
    MappingError,
    normalize_id,
    resolve_league,
    resolve_team,
    resolve_match,
    mapping_status,
)


class TeamMappingTests(unittest.TestCase):

    def setUp(self):
        self.leagues = {
            39: LeagueMapping(
                39, "PL", verified=True
            ),
        }

        self.teams = {
            ("PL", 100): TeamMapping(
                100, 200, "PL", verified=True
            ),
            ("PL", 101): TeamMapping(
                101, 201, "PL", verified=True
            ),
        }

        self.league_patch = patch.dict(
            "v84_team_mapping.LEAGUE_MAPPINGS",
            self.leagues,
            clear=True,
        )
        self.team_patch = patch.dict(
            "v84_team_mapping.TEAM_MAPPINGS",
            self.teams,
            clear=True,
        )

        self.league_patch.start()
        self.team_patch.start()

        self.addCleanup(self.league_patch.stop)
        self.addCleanup(self.team_patch.stop)

    def sample_match(self):
        return {
            "league_id": 39,
            "home_team_id": 100,
            "away_team_id": 101,
        }

    def test_valid_integer_id(self):
        self.assertEqual(normalize_id(100), 100)

    def test_numeric_string_id(self):
        self.assertEqual(normalize_id("100"), 100)

    def test_boolean_id_rejected(self):
        with self.assertRaises(MappingError):
            normalize_id(True)

    def test_zero_id_rejected(self):
        with self.assertRaises(MappingError):
            normalize_id(0)

    def test_negative_id_rejected(self):
        with self.assertRaises(MappingError):
            normalize_id(-5)

    def test_float_id_rejected(self):
        with self.assertRaises(MappingError):
            normalize_id(100.5)

    def test_verified_league_resolves(self):
        self.assertEqual(resolve_league(39), "PL")

    def test_unknown_league_rejected(self):
        with self.assertRaises(MappingError):
            resolve_league(999)

    def test_unverified_league_rejected(self):
        self.leagues[39] = LeagueMapping(
            39, "PL", verified=False
        )

        with self.assertRaises(MappingError):
            resolve_league(39)

    def test_verified_team_resolves(self):
        self.assertEqual(
            resolve_team(100, "PL"), 200
        )

    def test_unknown_team_rejected(self):
        with self.assertRaises(MappingError):
            resolve_team(999, "PL")

    def test_unverified_team_rejected(self):
        self.teams[("PL", 100)] = TeamMapping(
            100, 200, "PL", verified=False
        )

        with self.assertRaises(MappingError):
            resolve_team(100, "PL")

    def test_wrong_league_rejected(self):
        with self.assertRaises(MappingError):
            resolve_team(100, "PD")

    def test_valid_match_resolves(self):
        result = resolve_match(
            self.sample_match()
        )

        self.assertTrue(result["verified"])
        self.assertEqual(result["league"], "PL")
        self.assertEqual(result["home_id"], 200)
        self.assertEqual(result["away_id"], 201)

    def test_identical_teams_rejected(self):
        match = self.sample_match()
        match["away_team_id"] = 100

        with self.assertRaises(MappingError):
            resolve_match(match)

    def test_invalid_match_rejected(self):
        with self.assertRaises(MappingError):
            resolve_match(None)

    def test_mapping_status_ready(self):
        result = mapping_status(
            self.sample_match()
        )

        self.assertTrue(result["ready"])
        self.assertIsNotNone(result["mapping"])

    def test_mapping_status_unknown(self):
        result = mapping_status({
            "league_id": 999,
            "home_team_id": 100,
            "away_team_id": 101,
        })

        self.assertFalse(result["ready"])
        self.assertIsNone(result["mapping"])


if __name__ == "__main__":
    unittest.main()
