"""Offline V8.5 calibration research for Bundesliga binary markets only.

Protocol: 2023 trains calibrators, 2024 validates method choice, and 2025 is
exploratory only.  No live model, selection, or probability is modified.
"""

import hashlib
import json
import math
from pathlib import Path

from backtest_v84_calibration import chronological_rows, load_cached
from backtest_v84_phase2 import bootstrap_interval


LEAGUE = "BL1"
TRAIN, VALIDATION, EXPLORATORY = "2023", "2024", "2025"
MARKETS = ("over25", "btts")
EPSILON = 1e-8


def clip(value):
    return min(1 - EPSILON, max(EPSILON, float(value)))


def logit(value):
    value = clip(value)
    return math.log(value / (1 - value))


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-35, min(35, value))))


def fit_platt(rows, market, iterations=800, learning_rate=.05):
    """Fit a deterministic logistic calibration on training rows only."""
    if len(rows) < 30:
        raise ValueError("Insufficient calibration training sample")
    intercept, slope = 0.0, 1.0
    features = [(logit(row["prediction"][market]), row["outcome"][market]) for row in rows]
    for _ in range(iterations):
        errors = [sigmoid(intercept + slope * feature) - target for feature, target in features]
        intercept -= learning_rate * sum(errors) / len(errors)
        slope -= learning_rate * sum(error * feature for error, (feature, _) in zip(errors, features)) / len(errors)
    return {"method": "platt", "intercept": intercept, "slope": slope, "training_n": len(rows)}


def pav(points):
    """Pool-adjacent-violators isotonic fit: (probability, outcome) pairs."""
    blocks = []
    for value, target in sorted(points):
        blocks.append([value, value, 1, target])
        while len(blocks) > 1 and blocks[-2][3] / blocks[-2][2] > blocks[-1][3] / blocks[-1][2]:
            right, left = blocks.pop(), blocks.pop()
            blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
    return [{"low": low, "high": high, "value": total / count} for low, high, count, total in blocks]


def fit_isotonic(rows, market, min_sample=60):
    if len(rows) < min_sample:
        raise ValueError("Insufficient isotonic training sample")
    return {"method": "isotonic", "blocks": pav([(row["prediction"][market], row["outcome"][market]) for row in rows]), "training_n": len(rows)}


def apply(model, probability):
    probability = clip(probability)
    if model["method"] == "platt":
        return sigmoid(model["intercept"] + model["slope"] * logit(probability))
    for block in model["blocks"]:
        if probability <= block["high"]:
            return block["value"]
    return model["blocks"][-1]["value"]


def scores(rows, market, probabilities):
    if not rows:
        return {"n": 0, "brier": None, "log_loss": None, "ece": None}
    outcomes = [row["outcome"][market] for row in rows]
    brier = sum((probability - target) ** 2 for probability, target in zip(probabilities, outcomes)) / len(rows)
    loss = -sum(target * math.log(clip(probability)) + (1 - target) * math.log(clip(1 - probability)) for probability, target in zip(probabilities, outcomes)) / len(rows)
    bins = [[] for _ in range(10)]
    for probability, target in zip(probabilities, outcomes):
        bins[min(9, int(probability * 10))].append((probability, target))
    ece = sum(len(bucket) / len(rows) * abs(sum(p for p, _ in bucket) / len(bucket) - sum(y for _, y in bucket) / len(bucket)) for bucket in bins if bucket)
    return {"n": len(rows), "brier": brier, "log_loss": loss, "ece": ece}


def evaluate(rows, market, model=None):
    raw = [row["prediction"][market] for row in rows]
    baseline = [row["baseline"][market] for row in rows]
    calibrated = [apply(model, value) for value in raw] if model else None
    output = {"v8_raw": scores(rows, market, raw), "baseline": scores(rows, market, baseline), "calibrated": scores(rows, market, calibrated) if calibrated else None}
    if calibrated:
        outcome = [row["outcome"][market] for row in rows]
        output["paired_brier_delta_calibrated_minus_raw"] = bootstrap_interval([(calibrated[index] - outcome[index]) ** 2 - (raw[index] - outcome[index]) ** 2 for index in range(len(rows))], seed=31415)
        output["paired_brier_delta_calibrated_minus_baseline"] = bootstrap_interval([(calibrated[index] - outcome[index]) ** 2 - (baseline[index] - outcome[index]) ** 2 for index in range(len(rows))], seed=27182)
    return output


def data_manifest(cache_dir=Path("data_cache")):
    files = {}
    for season in (TRAIN, VALIDATION, EXPLORATORY):
        path = cache_dir / f"{LEAGUE}_{season}.json"
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"schema": 1, "league": LEAGUE, "markets": list(MARKETS), "train": TRAIN, "validation": VALIDATION, "exploratory": EXPLORATORY, "independent_holdout": "2026_or_later_unseen_period", "methods": {"platt": {"iterations": 800, "learning_rate": .05}, "isotonic": {"minimum_training_n": 60}}, "data_sha256": files, "live_model_changed": False}


def run():
    data = {season: chronological_rows(LEAGUE, load_cached(LEAGUE, season)) for season in (TRAIN, VALIDATION, EXPLORATORY)}
    output = {"manifest": data_manifest(), "results": {}}
    for market in MARKETS:
        models = {"platt": fit_platt(data[TRAIN], market), "isotonic": fit_isotonic(data[TRAIN], market)}
        output["results"][market] = {"train_n": len(data[TRAIN]), "validation": {name: evaluate(data[VALIDATION], market, model) for name, model in models.items()}, "exploratory_2025": {name: evaluate(data[EXPLORATORY], market, model) for name, model in models.items()}}
    return output


def main():
    print(json.dumps(run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
