"""AVAX FUTBOL ANALIZ PRO V8.2
Champions League V6/V7 model comparison.

2023: Model selection
2024: Validation
2025: Historical evaluation

Research only. No guaranteed accuracy.
"""

from collections import defaultdict
from pathlib import Path
import json
import math

from backtest_v6 import (
    valid,
    evaluate as evaluate_v6,
)
from backtest_v7 import (
    CONFIGS,
    evaluate as evaluate_v7,
)

LEAGUE = "CL"
SEASONS = ("2023", "2024", "2025")
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)

MARKETS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}


def load_matches(season):
    path = Path("data_cache") / (
        f"{LEAGUE}_{season}.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Missing cache: {path}. "
            "Run V8.2 data research first."
        )

    with path.open(encoding="utf-8") as file:
        raw = json.load(file)

    matches = valid(raw)

    if not matches:
        raise ValueError(
            f"No valid matches: {season}"
        )

    matches.sort(
        key=lambda m: (
            m["utcDate"],
            m["id"],
        )
    )

    return matches


def candidates(matches):
    """Run existing V6 and V7 candidates."""

    result = {}

    for weight in WEIGHTS:
        name = f"V6_{weight:.2f}"
        result[name] = evaluate_v6(
            matches, weight
        )

    for index, config in enumerate(CONFIGS):
        name = f"V7_{index:02d}"
        result[name] = evaluate_v7(
            matches, config
        )

    return result


def brier(rows, keys):
    if not rows:
        return float("inf")

    total = 0.0

    for probability, outcome in rows:
        total += sum(
            (
                float(probability[key])
                - float(outcome[key])
            ) ** 2
            for key in keys
        ) / len(keys)

    return total / len(rows)


def evaluate_season(matches):
    results = candidates(matches)
    scores = {}

    for model, rows in results.items():
        scores[model] = {
            market: brier(rows, keys)
            for market, keys in MARKETS.items()
        }

    return scores, {
        model: len(rows)
        for model, rows in results.items()
    }


def choose_models(scores):
    selected = {}

    for market in MARKETS:
        selected[market] = min(
            scores,
            key=lambda model: (
                scores[model][market],
                model,
            )
        )

    return selected


def show_results(season, scores, selected, counts):
    print("\n" + "=" * 55)
    print("AVAX V8.2 - CHAMPIONS LEAGUE")
    print("SEASON:", season)
    print("=" * 55)

    for market, model in selected.items():
        value = scores[model][market]

        print(
            f"{market}: {model}"
            f" | Brier={value:.4f}"
            f" | matches={counts[model]}"
        )

    print(
        "Note: Lower Brier is better."
    )


def main():
    print("AVAX V8.2 - MODEL COMPARISON")
    print("Competition:", LEAGUE)

    season_results = {}
    season_counts = {}

    for season in SEASONS:
        matches = load_matches(season)

        print(
            f"\nEvaluating {season}: "
            f"{len(matches)} matches",
            flush=True,
        )

        scores, counts = evaluate_season(
            matches
        )

        season_results[season] = scores
        season_counts[season] = counts

    training = season_results["2023"]

    selected = choose_models(training)

    print("\nSELECTED ON 2023 DATA")

    for market, model in selected.items():
        print(market, "=>", model)

    for season in SEASONS:
        show_results(
            season,
            season_results[season],
            selected,
            season_counts[season],
        )

    print("\n2025 COMPARISON AGAINST V6")

    for market, model in selected.items():
        baseline = min(
            (
                candidate
                for candidate in season_results["2025"]
                if candidate.startswith("V6_")
            ),
            key=lambda candidate:
                season_results["2023"][candidate][market]
        )

        old = season_results["2025"][
            baseline
        ][market]

        new = season_results["2025"][
            model
        ][market]

        print(
            market,
            "baseline=", baseline,
            f"{old:.4f}",
            "selected=", model,
            f"{new:.4f}",
            "delta=", f"{new-old:+.4f}",
        )

    print("\nResearch complete.")
    print(
        "Historical results are not "
        "independent proof of future accuracy."
    )


if __name__ == "__main__":
    main()
