"""AVAX FUTBOL ANALIZ PRO V8
Market-specific V6/V7 model selection and validation.

Run:
    python backtest_v8.py

Optional:
    python backtest_v8.py PL

Historical seasons have already been inspected.
This is NOT a fully independent holdout.
"""

import sys
from backtest_v6 import (
    LEAGUES, MARKETS, evaluate as evaluate_v6
)
from backtest_v7 import CONFIGS, evaluate_v7
from backtest_v73 import cached_fetch

SEASONS = ("2023", "2024", "2025")
V6_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)

GROUPS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}


def brier(rows, keys):
    if not rows:
        raise ValueError("No eligible predictions")
    return sum(
        (p[k] - y[k]) ** 2
        for p, y in rows
        for k in keys
    ) / (len(rows) * len(keys))


def accuracy(rows):
    keys = ("home", "draw", "away")
    return sum(
        max(keys, key=lambda k: p[k])
        == max(keys, key=lambda k: y[k])
        for p, y in rows
    ) / len(rows)


def candidates(matches):
    result = {}

    for weight in V6_WEIGHTS:
        name = f"V6_{weight:.2f}"
        result[name] = evaluate_v6(matches, weight)

    for index, config in enumerate(CONFIGS):
        name = f"V7_{index:02d}"
        result[name] = evaluate_v7(matches, config)

    counts = {len(rows) for rows in result.values()}
    if len(counts) != 1 or min(counts) < 50:
        raise ValueError("Inconsistent prediction coverage")

    outcomes = [
        [y for _, y in rows]
        for rows in result.values()
    ]
    if any(item != outcomes[0] for item in outcomes[1:]):
        raise ValueError("Prediction outcomes do not align")

    return result


def choose_models(training):
    selected = {}

    for group, keys in GROUPS.items():
        selected[group] = min(
            training,
            key=lambda name: (
                brier(training[name], keys),
                name
            )
        )

    return selected


def report(title, data, selected):
    print(f"\n{title}")

    for group, keys in GROUPS.items():
        name = selected[group]
        rows = data[name]
        score = brier(rows, keys)

        print(
            f"{group}: model={name} "
            f"| Brier={score:.4f} "
            f"| matches={len(rows)}"
        )

        if group == "match_result":
            print(
                f"  MS accuracy={accuracy(rows):.1%}"
            )


def run_league(code):
    print(f"\n{'=' * 45}")
    print(f"AVAX V8 - {LEAGUES[code]}")

    data = {}

    for season in SEASONS:
        matches = cached_fetch(code, season)
        if len(matches) < 100:
            raise ValueError(
                f"Insufficient matches: {season}"
            )
        data[season] = candidates(matches)

    selected = choose_models(data["2023"])

    report("TRAIN 2023", data["2023"], selected)
    report("VALIDATION 2024", data["2024"], selected)
    report("HISTORICAL TEST 2025", data["2025"], selected)

    print("\n2025 comparison against V6 baseline:")

    for group, keys in GROUPS.items():
        name = selected[group]
        chosen = brier(data["2025"][name], keys)
        baseline = brier(
            data["2025"]["V6_0.00"], keys
        )
        delta = chosen - baseline

        print(
            f"{group}: baseline={baseline:.4f} "
            f"| selected={chosen:.4f} "
            f"| delta={delta:+.4f}"
        )

    print(
        "Negative delta means lower Brier score."
    )


def main():
    code = (
        sys.argv[1].upper()
        if len(sys.argv) > 1
        else None
    )

    if code and code not in LEAGUES:
        raise SystemExit("Unknown league")

    codes = [code] if code else list(LEAGUES)
    failures = []

    for league in codes:
        try:
            run_league(league)
        except (
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
            OSError
        ) as exc:
            print(f"{league}: ERROR {exc}")
            failures.append(league)

    print("\nAVAX V8 historical research complete.")
    print(
        "Previously inspected seasons are not "
        "an independent holdout."
    )
    print(
        "No guaranteed accuracy or betting profit."
    )

    if failures:
        raise SystemExit(
            "Incomplete leagues: " + ", ".join(failures)
        )


if __name__ == "__main__":
    main()
