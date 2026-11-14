"""Resumable, quota-safe historical football-data.org cache collector.

Reads ``FOOTBALL_DATA_API_KEY`` only from the process environment.  It never
prints, stores, or returns that value.  Existing valid cache files are skipped.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from backtest_v6 import valid


API_URL = "https://api.football-data.org/v4"
CACHE_DIR = Path("data_cache")
LEAGUES = ("PL", "PD", "SA", "BL1", "FL1", "CL")
SEASONS = ("2023", "2024", "2025")
MIN_REQUEST_INTERVAL = 7.0


def cache_path(league, season, cache_dir=CACHE_DIR):
    if league not in LEAGUES or str(season) not in SEASONS:
        raise ValueError("Unsupported league or season")
    return cache_dir / f"{league}_{season}.json"


def validate_payload(payload):
    """Return valid finished fixtures, rejecting incomplete cache payloads."""
    if isinstance(payload, dict):
        payload = payload.get("matches")
    if not isinstance(payload, list):
        raise ValueError("Cache payload is not a list")
    if any(not isinstance(match, dict) or match.get("status") != "FINISHED" for match in payload):
        raise ValueError("Cache contains non-finished or invalid matches")
    fixtures = valid(payload)
    if len(fixtures) != len(payload) or not fixtures:
        raise ValueError("Cache contains invalid or empty fixtures")
    fixtures.sort(key=lambda match: (match["utcDate"], match["id"]))
    if len({match["id"] for match in fixtures}) != len(fixtures):
        raise ValueError("Cache contains duplicate match IDs")
    return fixtures


def read_valid_cache(league, season, cache_dir=CACHE_DIR):
    path = cache_path(league, season, cache_dir)
    if not path.is_file():
        return None
    try:
        return validate_payload(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def request_finished(league, season, api_key, opener=urllib.request.urlopen):
    """Make one provider request; callers decide retry and pacing."""
    query = urllib.parse.urlencode({"season": season, "status": "FINISHED"})
    request = urllib.request.Request(
        f"{API_URL}/competitions/{league}/matches?{query}",
        headers={"X-Auth-Token": api_key, "Accept": "application/json"},
    )
    with opener(request, timeout=30) as response:
        payload = json.load(response)
    matches = payload.get("matches") if isinstance(payload, dict) else None
    if not isinstance(matches, list):
        raise ValueError("Invalid provider response")
    return matches


def atomic_save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def collect_one(league, season, *, cache_dir=CACHE_DIR, opener=urllib.request.urlopen, sleep=time.sleep, now=time.monotonic, last_request=None):
    """Collect one cache entry, returning safe status metadata only."""
    cached = read_valid_cache(league, season, cache_dir)
    if cached is not None:
        return {"status": "cached", "league": league, "season": season, "matches": len(cached), "last_request": last_request}
    key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not key:
        return {"status": "missing_api_key", "league": league, "season": season, "matches": None, "last_request": last_request}
    if last_request is not None:
        sleep(max(0.0, MIN_REQUEST_INTERVAL - (now() - last_request)))
    try:
        raw = request_finished(league, season, key, opener)
    except urllib.error.HTTPError as error:
        status = "forbidden" if error.code == 403 else "rate_limited" if error.code == 429 else "http_error"
        retry_after = None
        if error.code == 429:
            try:
                retry_after = max(MIN_REQUEST_INTERVAL, float(error.headers.get("Retry-After", MIN_REQUEST_INTERVAL)))
            except (ValueError, TypeError, AttributeError):
                retry_after = MIN_REQUEST_INTERVAL
        return {"status": status, "http_status": error.code, "league": league, "season": season, "matches": None, "retry_after": retry_after, "last_request": now()}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {"status": "network_or_response_error", "league": league, "season": season, "matches": None, "last_request": now()}
    try:
        fixtures = validate_payload(raw)
    except ValueError:
        return {"status": "empty_or_invalid", "league": league, "season": season, "matches": 0, "last_request": now()}
    atomic_save(cache_path(league, season, cache_dir), raw)
    return {"status": "downloaded", "http_status": 200, "league": league, "season": season, "matches": len(fixtures), "last_request": now()}


def collect_all():
    last_request = None
    for league in LEAGUES:
        for season in SEASONS:
            result = collect_one(league, season, last_request=last_request)
            last_request = result.pop("last_request")
            # Safe machine-readable output; never includes request headers or key.
            print(json.dumps(result, ensure_ascii=False))
            if result["status"] == "missing_api_key":
                return
            if result["status"] == "rate_limited":
                time.sleep(result["retry_after"])


def main():
    parser = argparse.ArgumentParser(description="Resumable V8 historical cache collector")
    parser.add_argument("--check-only", action="store_true", help="Report cache state without API requests")
    args = parser.parse_args()
    if args.check_only:
        for league in LEAGUES:
            for season in SEASONS:
                cached = read_valid_cache(league, season)
                print(json.dumps({"league": league, "season": season, "status": "cached" if cached else "missing_or_invalid_cache", "matches": len(cached) if cached else None}, ensure_ascii=False))
        return
    collect_all()


if __name__ == "__main__":
    main()
