
"""AVAX V8.4 - Safe Mapping Verifier.

Compare team identities from two football data providers.

This module:
- Finds possible team matches.
- Rejects ambiguous or conflicting identities.
- Requires explicit manual verification.
- Never automatically activates a mapping.
- Makes no API requests.
- Does not modify live V8.3.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


class VerificationError(ValueError):
    """Invalid or unsafe mapping verification."""


@dataclass(frozen=True)
class TeamIdentity:
    provider: str
    team_id: int
    name: str
    country: str
    league: str


@dataclass(frozen=True)
class MappingCandidate:
    source: TeamIdentity
    target: TeamIdentity
    similarity: float
    status: str = "PENDING"


def normalize_name(value):
    """Normalize names for comparison only."""

    if not isinstance(value, str):
        return ""

    value = unicodedata.normalize(
        "NFKD", value.casefold()
    )

    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    value = re.sub(
        r"[^a-z0-9]+", " ", value
    )

    return " ".join(value.split())


def validate_identity(identity):
    """Validate a provider team identity."""

    if not isinstance(identity, TeamIdentity):
        raise VerificationError(
            "Invalid team identity"
        )

    if identity.provider not in {
        "api-football",
        "football-data",
    }:
        raise VerificationError(
            "Unknown provider"
        )

    if (
        not isinstance(identity.team_id, int)
        or isinstance(identity.team_id, bool)
        or identity.team_id <= 0
    ):
        raise VerificationError(
            "Invalid team ID"
        )

    for value in (
        identity.name,
        identity.country,
        identity.league,
    ):
        if not isinstance(value, str) or not value.strip():
            raise VerificationError(
                "Missing identity information"
            )

    return identity


def similarity_score(source, target):
    """Calculate name similarity, not verification."""

    validate_identity(source)
    validate_identity(target)

    left = normalize_name(source.name)
    right = normalize_name(target.name)

    if not left or not right:
        return 0.0

    return round(
        SequenceMatcher(
            None, left, right
        ).ratio(),
        4,
    )


def compare_teams(source, target):
    """Create a pending candidate if context matches."""

    validate_identity(source)
    validate_identity(target)

    if source.provider != "api-football":
        raise VerificationError(
            "Source must be API-Football"
        )

    if target.provider != "football-data":
        raise VerificationError(
            "Target must be football-data"
        )

    if (
        normalize_name(source.country)
        != normalize_name(target.country)
    ):
        raise VerificationError(
            "Country mismatch"
        )

    if (
        normalize_name(source.league)
        != normalize_name(target.league)
    ):
        raise VerificationError(
            "League mismatch"
        )

    return MappingCandidate(
        source=source,
        target=target,
        similarity=similarity_score(
            source, target
        ),
        status="PENDING",
    )


def find_candidates(
    source,
    targets,
    minimum_similarity=0.60,
):
    """Find possible matches without approving them."""

    validate_identity(source)

    if source.provider != "api-football":
        raise VerificationError(
            "Invalid source provider"
        )

    if (
        not isinstance(minimum_similarity, (int, float))
        or isinstance(minimum_similarity, bool)
        or not 0 <= minimum_similarity <= 1
    ):
        raise VerificationError(
            "Invalid similarity threshold"
        )

    if not isinstance(targets, (list, tuple)):
        raise VerificationError(
            "Targets must be a list or tuple"
        )

    candidates = []

    for target in targets:
        try:
            candidate = compare_teams(
                source, target
            )
        except VerificationError:
            continue

        if candidate.similarity >= minimum_similarity:
            candidates.append(candidate)

    return sorted(
        candidates,
        key=lambda item: (
            -item.similarity,
            item.target.team_id,
        ),
    )


def verification_report(candidate):
    """Produce a manual-review report."""

    if not isinstance(candidate, MappingCandidate):
        raise VerificationError(
            "Invalid mapping candidate"
        )

    validate_identity(candidate.source)
    validate_identity(candidate.target)

    if candidate.status != "PENDING":
        raise VerificationError(
            "Unexpected candidate status"
        )

    return {
        "source_provider": candidate.source.provider,
        "source_id": candidate.source.team_id,
        "source_name": candidate.source.name,
        "target_provider": candidate.target.provider,
        "target_id": candidate.target.team_id,
        "target_name": candidate.target.name,
        "similarity": candidate.similarity,
        "status": "PENDING",
        "verified": False,
        "requires_manual_review": True,
        "warning": (
            "Name similarity does not prove identity. "
            "Verify both provider records manually."
        ),
    }


def can_activate_mapping(report):
    """Never activate a pending or unverified mapping."""

    if not isinstance(report, dict):
        return False

    return False
