"""Offline guardrails for a frozen 2026 independent V8 evaluation.

This module fetches nothing and evaluates nothing. It verifies that a future
holdout payload contains only completed 2026 fixtures and that V8 selections
still match the pre-holdout manifest.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from backtest_v6 import valid
from v8_models import MODEL_SELECTIONS


MANIFEST_PATH = Path("v86_holdout_manifest.json")


def selection_fingerprint(selections=MODEL_SELECTIONS):
    encoded = json.dumps(selections, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone missing")
    return parsed.astimezone(timezone.utc)


def validate_holdout_rows(rows, as_of=None):
    """Accept only completed, unique, chronological 2026 fixtures."""
    if not isinstance(rows, list):
        raise ValueError("Holdout payload is not a list")
    if any(not isinstance(row, dict) or row.get("status") != "FINISHED" for row in rows):
        raise ValueError("Holdout includes non-finished fixtures")
    fixtures = valid(rows)
    if len(fixtures) != len(rows):
        raise ValueError("Holdout includes invalid fixtures")
    if len({row["id"] for row in fixtures}) != len(fixtures):
        raise ValueError("Holdout includes duplicate match IDs")
    cutoff = parse_utc(as_of) if as_of else datetime.now(timezone.utc)
    for row in fixtures:
        kickoff = parse_utc(row["utcDate"])
        if kickoff.year != 2026:
            raise ValueError("Holdout includes non-2026 fixture")
        if kickoff > cutoff:
            raise ValueError("Holdout includes future fixture")
    return sorted(fixtures, key=lambda row: (parse_utc(row["utcDate"]), row["id"]))


def verify_manifest(manifest_path=MANIFEST_PATH):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("selection_fingerprint") != selection_fingerprint():
        raise ValueError("V8 model selections changed after holdout freeze")
    if manifest.get("holdout_year") != 2026 or manifest.get("allow_download") is not False:
        raise ValueError("Invalid holdout manifest")
    return manifest
