"""Second-stage offline V8 performance research.

Uses only cached finished fixtures and the unchanged V8 selections.  Bootstrap
intervals are descriptive paired-match intervals, not betting-profit claims.
"""

import json
import random

from backtest_v84_calibration import (
    GROUPS, LEAGUES, SEASONS, brier, chronological_rows, load_cached, log_loss,
)


BOOTSTRAPS = 500
QUALITY_LEVELS = ("LOW", "MODERATE", "ADEQUATE")


def stable_seed(*values):
    return 1000 + sum((index + 1) * ord(char) for index, value in enumerate(values) for char in str(value))


def paired_brier_delta(rows, keys):
    """V8 minus chronological reference loss per fixture (negative is better)."""
    return [
        sum((row["prediction"][key] - row["outcome"][key]) ** 2 - (row["baseline"][key] - row["outcome"][key]) ** 2 for key in keys) / len(keys)
        for row in rows
    ]


def bootstrap_interval(values, samples=BOOTSTRAPS, seed=20261114):
    if not values:
        return None
    rng = random.Random(seed)
    size = len(values)
    means = sorted(sum(values[rng.randrange(size)] for _ in range(size)) / size for _ in range(samples))
    return {"mean_delta": sum(values) / size, "ci95_low": means[int(.025 * samples)], "ci95_high": means[int(.975 * samples)]}


def high_probability(rows, keys, threshold=.70):
    selected = []
    for row in rows:
        if len(keys) == 1:
            key = keys[0]
            if row["prediction"][key] >= threshold:
                selected.append((row["prediction"][key], row["outcome"][key]))
        else:
            key = max(keys, key=lambda item: row["prediction"][item])
            if row["prediction"][key] >= threshold:
                selected.append((row["prediction"][key], row["outcome"][key]))
    if not selected:
        return {"n": 0, "mean_prediction": None, "observed_rate": None}
    return {"n": len(selected), "mean_prediction": sum(p for p, _ in selected) / len(selected), "observed_rate": sum(y for _, y in selected) / len(selected)}


def market_report(rows, keys, seed):
    return {
        "n": len(rows), "v8_brier": brier(rows, "prediction", keys),
        "baseline_brier": brier(rows, "baseline", keys),
        "v8_log_loss": log_loss(rows, "prediction", keys),
        "baseline_log_loss": log_loss(rows, "baseline", keys),
        "paired_brier_delta": bootstrap_interval(paired_brier_delta(rows, keys), seed=seed),
        "high_probability": high_probability(rows, keys),
    }


def season_report(league, season):
    rows = chronological_rows(league, load_cached(league, season))
    quality = {}
    for level in QUALITY_LEVELS:
        subset = [row for row in rows if row["quality"] == level]
        quality[level] = {group: market_report(subset, keys, stable_seed(league, season, level, group)) for group, keys in GROUPS.items()}
    return {
        "league": league, "season": season, "n": len(rows),
        "markets": {group: market_report(rows, keys, stable_seed(league, season, group)) for group, keys in GROUPS.items()},
        "quality": quality,
    }


def all_reports():
    return [season_report(league, season) for league in LEAGUES for season in SEASONS]


def main():
    print(json.dumps(all_reports(), ensure_ascii=False))


if __name__ == "__main__":
    main()
