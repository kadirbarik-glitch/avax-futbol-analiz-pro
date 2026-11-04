"""AVAX V7.3 - Multi-season V6/V7 comparison.
Run: python backtest_v73.py [PL|PD|SA|BL1|FL1]
Requires FOOTBALL_DATA_API_KEY.
Historical results are exploratory, not betting advice.
"""
import sys
import time
import random
from backtest_v6 import LEAGUES, MARKETS, fetch, valid, evaluate as v6_evaluate
from backtest_v7 import CONFIGS, evaluate_v7

SEASONS = ('2022', '2023', '2024', '2025')
V6_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
GROUPS = (
    ('match_result', ('home', 'draw', 'away')),
    ('over25', ('over25',)),
    ('btts', ('btts',)),
    ('all_markets', MARKETS),
)
BOOTSTRAPS = 1000
BLOCK_SIZE = 10


def brier(rows, keys):
    if not rows:
        raise ValueError('No eligible matches')
    return sum(
        (p[k] - y[k]) ** 2
        for p, y in rows for k in keys
    ) / (len(rows) * len(keys))


def accuracy(rows):
    keys = ('home', 'draw', 'away')
    return sum(
        max(keys, key=lambda k: p[k]) ==
        max(keys, key=lambda k: y[k])
        for p, y in rows
    ) / len(rows)


def paired(old, new, keys):
    if len(old) != len(new) or len(old) < 50:
        raise ValueError('Insufficient or mismatched predictions')
    result = []
    for (p0, y0), (p1, y1) in zip(old, new):
        if y0 != y1:
            raise ValueError('Outcome mismatch')
        result.append(
            sum(
                (p1[k] - y1[k]) ** 2 -
                (p0[k] - y0[k]) ** 2
                for k in keys
            ) / len(keys)
        )
    return result


def interval(values, seed):
    n = len(values)
    block = min(BLOCK_SIZE, n)
    rng = random.Random(seed)
    samples = []
    for _ in range(BOOTSTRAPS):
        total = []
        while len(total) < n:
            start = rng.randrange(n - block + 1)
            total.extend(values[start:start + block])
        samples.append(sum(total[:n]) / n)
    samples.sort()
    return (
        samples[int(0.025 * BOOTSTRAPS)],
        samples[int(0.975 * BOOTSTRAPS)],
    )


def choose(train):
    if len(train) < 100:
        raise ValueError('Insufficient training matches')
    weight = min(
        V6_WEIGHTS,
        key=lambda w: brier(v6_evaluate(train, w), MARKETS),
    )
    config = min(
        CONFIGS,
        key=lambda c: brier(evaluate_v7(train, c), MARKETS),
    )
    return weight, config


def run_pair(code, train_year, test_year, train, test):
    weight, config = choose(train)
    old = v6_evaluate(test, weight)
    new = evaluate_v7(test, config)
    paired(old, new, MARKETS)

    print(
        f'\n{LEAGUES[code]} | train={train_year} '
        f'-> test={test_year} | n={len(old)}'
    )
    print(f'V6 blend={weight:.2f} | V7 config={config}')
    print(
        f'MS accuracy: V6={accuracy(old):.1%} | '
        f'V7={accuracy(new):.1%}'
    )

    results = {}
    for i, (label, keys) in enumerate(GROUPS):
        changes = paired(old, new, keys)
        lo, hi = interval(
            changes, seed=2026 + i + int(test_year) * 11
        )
        delta = sum(changes) / len(changes)
        results[label] = (len(changes), delta)
        print(
            f'{label}: V6={brier(old, keys):.4f} | '
            f'V7={brier(new, keys):.4f} | '
            f'delta={delta:+.4f} | '
            f'approx 95% block interval=[{lo:+.4f},{hi:+.4f}]'
        )
    return results


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected and selected not in LEAGUES:
        raise SystemExit('Unknown league code')

    codes = [selected] if selected else list(LEAGUES)
    completed = 0
    failed = []
    aggregates = {label: [] for label, _ in GROUPS}
    calls = 0

    for code in codes:
        data = {}
        for season in SEASONS:
            if calls:
                time.sleep(7)
            calls += 1
            try:
                data[season] = valid(fetch(code, season))
            except RuntimeError as exc:
                print(f'{code} {season}: API ERROR {exc}')
                data[season] = None

        for train_year, test_year in zip(SEASONS, SEASONS[1:]):
            if data[train_year] is None or data[test_year] is None:
                failed.append(f'{code}:{train_year}->{test_year}')
                continue

            try:
                result = run_pair(
                    code, train_year, test_year,
                    data[train_year], data[test_year]
                )
                for label, (n, delta) in result.items():
                    aggregates[label].append((n, delta))
                completed += 1
            except (RuntimeError, ValueError) as exc:
                print(f'{code} {train_year}->{test_year}: ERROR {exc}')
                failed.append(f'{code}:{train_year}->{test_year}')

    print('\nWEIGHTED SUMMARY')
    for label, entries in aggregates.items():
        if entries:
            n = sum(x for x, _ in entries)
            delta = sum(x * d for x, d in entries) / n
            print(
                f'{label}: observations={n} | '
                f'weighted delta(V7-V6)={delta:+.4f}'
            )

    print(f'Completed: {completed}; incomplete: {len(failed)}')
    print('Negative delta favors V7.')
    print('Bootstrap is approximate; team dependence remains.')
    print('Historical results do not guarantee profitability.')

    if failed:
        raise SystemExit('Incomplete: ' + ', '.join(failed))


if __name__ == '__main__':
    main()

