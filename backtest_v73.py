"""AVAX V7.3: exploratory walk-forward V6/V7 comparison across 2023-2025.
Run: python backtest_v73.py [PL|PD|SA|BL1|FL1]
Requires FOOTBALL_DATA_API_KEY for uncached seasons.
Previous seasons select models; the following season evaluates unchanged settings.
Historical data have been inspected; this is not an independent holdout.
"""
import json
import random
import sys
import time
from pathlib import Path
from backtest_v6 import LEAGUES, MARKETS, fetch, valid, evaluate as v6_evaluate
from backtest_v7 import CONFIGS, evaluate_v7

SEASONS = ('2023', '2024', '2025')
V6_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
GROUPS = (('match_result', ('home', 'draw', 'away')),
          ('over25', ('over25',)), ('btts', ('btts',)),
          ('all_markets', MARKETS))
BOOTSTRAPS = 1000
BLOCK_SIZE = 10
CACHE_DIR = Path('data_cache')
API_INTERVAL = 7.0
_last_request = None


def cached_fetch(code, season):
    """Cache validated season fixtures; only wait for actual API requests."""
    global _last_request
    path = CACHE_DIR / f'{code}_{season}.json'
    if path.is_file():
        try:
            with path.open(encoding='utf-8') as handle:
                cached = json.load(handle)
            fixtures = valid(cached)
            print(f'{code} {season}: CACHE HIT', flush=True)
            return fixtures
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(f'{code} {season}: invalid cache ({exc}); downloading again', flush=True)
    if _last_request is not None:
        time.sleep(max(0.0, API_INTERVAL - (time.monotonic() - _last_request)))
    _last_request = time.monotonic()
    raw = fetch(code, season)
    fixtures = valid(raw)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(raw, handle)
        temporary.replace(path)
    except (OSError, TypeError) as exc:
        temporary.unlink(missing_ok=True)
        print(f'{code} {season}: cache write skipped ({exc})', flush=True)
    return fixtures


def brier(rows, keys):
    if not rows:
        raise ValueError('No eligible matches')
    return sum((p[k] - y[k]) ** 2 for p, y in rows for k in keys) / (len(rows) * len(keys))


def accuracy(rows):
    keys = ('home', 'draw', 'away')
    return sum(max(keys, key=lambda k: p[k]) == max(keys, key=lambda k: y[k])
               for p, y in rows) / len(rows)


def paired(old, new, keys):
    if len(old) != len(new) or len(old) < 50:
        raise ValueError('Insufficient or mismatched predictions')
    result = []
    for (p0, y0), (p1, y1) in zip(old, new):
        if y0 != y1:
            raise ValueError('Outcome mismatch: cannot pair predictions')
        result.append(sum((p1[k] - y1[k]) ** 2 - (p0[k] - y0[k]) ** 2
                          for k in keys) / len(keys))
    return result


def interval(values, seed):
    """Approximate moving-block interval; shared-team dependence remains."""
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
    return samples[int(0.025 * BOOTSTRAPS)], samples[int(0.975 * BOOTSTRAPS)]


def choose(train):
    if len(train) < 100:
        raise ValueError('Insufficient training matches')
    v6_weight = min(V6_WEIGHTS, key=lambda w: brier(v6_evaluate(train, w), MARKETS))
    v7_config = min(CONFIGS, key=lambda c: brier(evaluate_v7(train, c), MARKETS))
    return v6_weight, v7_config


def run_pair(code, training_year, testing_year, train, test):
    weight, config = choose(train)
    old = v6_evaluate(test, weight)
    new = evaluate_v7(test, config)
    # Same fixture order is assumed; outcome equality alone cannot prove ID alignment.
    paired(old, new, MARKETS)
    print(f'\n{LEAGUES[code]} | train={training_year} -> test={testing_year} | n={len(old)}')
    print(f'V6 blend={weight:.2f} | V7 config={config}')
    print(f'MS accuracy: V6={accuracy(old):.1%} | V7={accuracy(new):.1%}')
    results = {}
    for i, (label, keys) in enumerate(GROUPS):
        changes = paired(old, new, keys)
        lo, hi = interval(changes, seed=2026 + i + int(testing_year) * 11)
        delta = sum(changes) / len(changes)
        results[label] = (len(changes), delta)
        print(f'{label}: V6={brier(old, keys):.4f} | V7={brier(new, keys):.4f} | '
              f'delta={delta:+.4f} | approx 95% block interval=[{lo:+.4f},{hi:+.4f}]')
    return results


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected and selected not in LEAGUES:
        raise SystemExit('Usage: python backtest_v73.py [PL|PD|SA|BL1|FL1]')
    codes = [selected] if selected else list(LEAGUES)
    completed = 0
    failed = []
    aggregates = {label: [] for label, _ in GROUPS}
    for code in codes:
        data = {}
        for season in SEASONS:
            try:
                data[season] = cached_fetch(code, season)
            except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
                print(f'{code} {season}: DATA ERROR {exc}', flush=True)
                data[season] = None
        for train_year, test_year in zip(SEASONS, SEASONS[1:]):
            if data[train_year] is None or data[test_year] is None:
                failed.append(f'{code}:{train_year}->{test_year}')
                continue
            try:
                result = run_pair(code, train_year, test_year,
                                  data[train_year], data[test_year])
                for label, (n, delta) in result.items():
                    aggregates[label].append((n, delta))
                completed += 1
            except (RuntimeError, ValueError, TypeError, KeyError) as exc:
                print(f'{code} {train_year}->{test_year}: ERROR {exc}', flush=True)
                failed.append(f'{code}:{train_year}->{test_year}')
    print('\nWEIGHTED SUMMARY (descriptive only; no pooled confidence interval)')
    for label, entries in aggregates.items():
        if entries:
            n = sum(x for x, _ in entries)
            delta = sum(x * d for x, d in entries) / n
            print(f'{label}: paired observations={n} | weighted delta(V7-V6)={delta:+.4f}')
    print(f'Completed comparisons: {completed}; incomplete: {len(failed)}')
    print('Negative delta favors V7. Model selection and prior inspections limit independence.')
    print('Bootstrap is approximate and does not fully account for team clustering or multiple testing.')
    print('No proof of betting profitability or guaranteed prediction accuracy.')
    if failed:
        raise SystemExit('Incomplete: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
