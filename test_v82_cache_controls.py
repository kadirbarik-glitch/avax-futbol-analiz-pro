"""Offline safety tests for Champions League cache controls."""

import hashlib
import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

import backtest_v82


def raw_match(match_id):
    return {
        "id": match_id,
        "utcDate": "2025-01-01T20:00:00Z",
        "status": "FINISHED",
        "homeTeam": {"id": 1},
        "awayTeam": {"id": 2},
        "score": {"fullTime": {"home": 1, "away": 0}},
    }


class CacheControlTests(unittest.TestCase):

    def test_offline_missing_cache_never_calls_fetch(self):
        cache_dir = MagicMock()
        path = MagicMock()
        cache_dir.__truediv__.return_value = path
        path.exists.return_value = False

        with patch.object(
            backtest_v82, "CACHE_DIR", cache_dir
        ), patch.object(backtest_v82, "fetch") as fetch:
            with self.assertRaisesRegex(
                RuntimeError, "--download"
            ):
                backtest_v82.load_season("2023", False)

        fetch.assert_not_called()

    def test_offline_valid_cache_is_loaded_without_fetch(self):
        cache_dir = MagicMock()
        path = MagicMock()
        cache_dir.__truediv__.return_value = path
        path.exists.return_value = True
        path.open.return_value = mock_open(
            read_data=json.dumps([raw_match(1)])
        )()

        with patch.object(
            backtest_v82, "CACHE_DIR", cache_dir
        ), patch.object(backtest_v82, "fetch") as fetch:
            matches, downloaded = backtest_v82.load_season(
                "2023", False
            )

        self.assertEqual(len(matches), 1)
        self.assertFalse(downloaded)
        fetch.assert_not_called()

    def test_manifest_records_all_cache_checksums(self):
        cache_dir = MagicMock()
        paths = {}

        for index, season in enumerate(backtest_v82.SEASONS):
            path = MagicMock()
            path.name = f"CL_{season}.json"
            path.read_bytes.return_value = json.dumps(
                [raw_match(index + 1)]
            ).encode("utf-8")
            paths[path.name] = path

        temporary = MagicMock()
        paths["CL_manifest.json.tmp"] = temporary
        paths["CL_manifest.json"] = MagicMock()
        cache_dir.__truediv__.side_effect = paths.__getitem__

        with patch.object(backtest_v82, "CACHE_DIR", cache_dir):
            backtest_v82.write_manifest()

        manifest = json.loads(
            temporary.write_text.call_args.args[0]
        )

        self.assertEqual(manifest["competition"], "CL")
        self.assertEqual(
            set(manifest["seasons"]), set(backtest_v82.SEASONS)
        )

        for season in backtest_v82.SEASONS:
            raw_bytes = paths[f"CL_{season}.json"].read_bytes()
            self.assertEqual(
                manifest["seasons"][season]["sha256"],
                hashlib.sha256(raw_bytes).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
