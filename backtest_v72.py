"""AVAX V7.2: walk-forward V6 vs V7 comparison, chronological block bootstrap.
Run: python backtest_v72.py [PL|PD|SA|BL1|FL1]
Requires FOOTBALL_DATA_API_KEY. Training 2023 -> testing 2024 and
training 2024 -> testing 2025. Each season's predictor resets its history.
2025 has already been inspected in prior experiments: not a pristine holdout.
"""
import sys
import time
import random
from backtest_v6 import LEAGUES, MARKETS, fetch, valid, evaluate as v6_evaluate
from backtest_v7 import CONFIGS, evaluate_v7

SEASONS = ('2023', '2024', '2025')
V6_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
BLOCK_SIZE = 10
BOOTSTRAPS = 1000


def brier(rows, keys=MARKETS):
    if not rows:
        raise ValueError('No eligible matches')
    return sum((p[k] - y[k]) ** 2 for p, y in rows for k in keys) / (len(rows) * len(keys))


def accuracy(rows):
    outcomes = ('home', 'draw', 'away')
    return sum(max(outcomes, key=lambda k: p[k]) == max(outcomes, key=lambda k: y[k])
               for p, y in rows) / len(rows)


def paired_differences(old, new, keys):
    if len(old) != len(new) or not old:
        raise ValueError('Mismatched or empty prediction coverage')
    differences = []
    for (p0, y0), (p1, y1) in zip(old, new):
        if y0 != y1:
            raise ValueError('Different match outcomes in aligned predictions')
        differences.append(sum((p1[k] - y1[k]) ** 2 - (p0[k] - y0[k]) ** 2
                               for k in keys) / len(keys))
    return differences


def block_interval(differences, seed):
    """Moving-block bootstrap; captures some local time dependence, not team clustering."""
    n = len(differences)
    size = min(BLOCK_SIZE, n)
    rng = random.Random(seed)
    estimates = []
    for _ in range(BOOTSTRAPS):
        sample = []
        while len(sample) < n:
            start = rng.randrange(n - size + 1)
            sample.extend(differences[start:start + size])
        estimates.append(sum(sample[:n]) / n)
    estimates.sort()
    return estimates[int(0.025 * BOOTSTRAPS)], estimates[int(0.975 * BOOTSTRAPS)]


def choose_models(train):
    if len(train) < 100:
        raise ValueError('Insufficient training fixtures')
    v6_trials = [(brier(v6_evaluate(train, weight)), weight) for weight in V6_WEIGHTS]
    v7_trials = [(brier(evaluate_v7(train, config)), config) for config in CONFIGS]
    return min(v6_trials)[1], min(v7_trials)[1]


def compare(code, train_year, test_year, train, test):
    v6_weight, v7_config = choose_models(train)
    old = v6_evaluate(test, v6_weight)
    new = evaluate_v7(test, v7_config)
    if len(old) < 50:
        raise ValueError('Insufficient test predictions')
    print(f'\n{LEAGUES[code]} | train={train_year} | test={test_year} | matches={len(old)}')
    print(f'V6 blend={v6_weight} | V7 config={v7_config}')
    print(f'MS accuracy: V6={accuracy(old):.1%} | V7={accuracy(new):.1%}')
    groups = [('all', MARKETS), ('match_result', ('home', 'draw', 'away')),
              ('over25', ('over25',)), ('btts', ('btts',))]
    for index, (label, keys) in enumerate(groups):
        diffs = paired_differences(old, new, keys)
        low, high = block_interval(diffs, seed=2026 + index)
        delta = sum(diffs) / len(diffs)
        print(f'{label}: V6={brier(old, keys):.4f} | V7={brier(new, keys):.4f} | '
              f'delta(V7-V6)={delta:+.4f} | 95% block interval=[{low:+.4f}, {high:+.4f}]')
    print('Negative delta favors V7; interval spanning zero is inconclusive.')


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected and selected not in LEAGUES:
        raise SystemExit('Usage: python backtest_v72.py [PL|PD|SA|BL1|FL1]')
    codes = [selected] if selected else list(LEAGUES)
    completed = 0
    failures = []
    requests_made = 0
    for code in codes:
        seasons = {}
        for year in SEASONS:
            if requests_made:
                time.sleep(7)
            requests_made += 1
            try:
                seasons[year] = valid(fetch(code, year))
            except RuntimeError as exc:
                print(f'{code} {year}: API ERROR: {exc}', flush=True)
                seasons[year] = None
        for train_year, test_year in zip(SEASONS, SEASONS[1:]):
            if seasons[train_year] is None or seasons[test_year] is None:
                failures.append(f'{code}:{train_year}->{test_year}')
                continue
            try:
                compare(code, train_year, test_year, seasons[train_year], seasons[test_year])
                completed += 1
            except (ValueError, RuntimeError) as exc:
                print(f'{code} {train_year}->{test_year}: ERROR: {exc}', flush=True)
                failures.append(f'{code}:{train_year}->{test_year}')
    print(f'\nCompleted comparisons: {completed}; incomplete: {len(failures)}')
    print('2025 was inspected during prior model development; it is not an untouched holdout.')
    print('Block bootstrap is approximate; teams share matches and time dependence remains.')
    print('Historical scores do not establish betting profitability or guarantee outcomes.')
    if failures:
        raise SystemExit('Incomplete: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
