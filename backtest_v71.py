"""AVAX V7.1: paired tuned V6 vs tuned V7 holdout evaluation.
Run: python backtest_v71.py [PL|PD|SA|BL1|FL1]
Requires FOOTBALL_DATA_API_KEY. 2024 tunes both models; 2025 is held out.
"""
import random
import sys
import time
from backtest_v6 import LEAGUES, MARKETS, fetch, valid, evaluate as evaluate_v6
from backtest_v7 import CONFIGS, evaluate_v7, brier, accuracy

TRAIN = '2024'
TEST = '2025'
V6_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
BOOTSTRAPS = 2000


def loss_by_match(rows):
    return [sum((p[k] - y[k]) ** 2 for k in MARKETS) / len(MARKETS)
            for p, y in rows]


def paired_interval(v6_rows, v7_rows):
    old = loss_by_match(v6_rows)
    new = loss_by_match(v7_rows)
    differences = [n - o for o, n in zip(old, new)]
    rng = random.Random(20261104)
    n = len(differences)
    samples = []
    for _ in range(BOOTSTRAPS):
        samples.append(sum(differences[rng.randrange(n)] for _ in range(n)) / n)
    samples.sort()
    return sum(differences) / n, samples[int(.025 * BOOTSTRAPS)], samples[int(.975 * BOOTSTRAPS)]


def assert_paired(v6_rows, v7_rows):
    if len(v6_rows) != len(v7_rows) or len(v6_rows) < 50:
        raise ValueError('Unequal or insufficient test coverage')
    # Both evaluators process matches in kickoff order and use the same 3-match eligibility.
    # Verify outcome vectors agree for each position before comparing losses.
    for (_, old_actual), (_, new_actual) in zip(v6_rows, v7_rows):
        if old_actual != new_actual:
            raise ValueError('Test match alignment differs')


def run_league(code):
    train = valid(fetch(code, TRAIN))
    time.sleep(7)
    test = valid(fetch(code, TEST))
    if len(train) < 100 or len(test) < 100:
        raise ValueError('Insufficient season data')

    v6_train = [(brier(evaluate_v6(train, w)), w) for w in V6_WEIGHTS]
    _, v6_weight = min(v6_train)
    v7_train = [(brier(evaluate_v7(train, cfg)), cfg) for cfg in CONFIGS]
    _, v7_config = min(v7_train)

    old = evaluate_v6(test, v6_weight)
    new = evaluate_v7(test, v7_config)
    assert_paired(old, new)
    delta, low, high = paired_interval(old, new)
    print(f'\n{LEAGUES[code]} | train={TRAIN} | holdout={TEST} | paired matches={len(old)}')
    print(f'Tuned V6 blend={v6_weight:.2f}; tuned V7 config={v7_config}')
    print(f'V6 Brier={brier(old):.4f} | V7 Brier={brier(new):.4f}')
    print(f'V6 accuracy={accuracy(old):.1%} | V7 accuracy={accuracy(new):.1%}')
    print(f'Paired Brier difference (V7-V6)={delta:+.4f}; '
          f'95% match-bootstrap interval=[{low:+.4f}, {high:+.4f}]')
    for key in MARKETS:
        v6_loss = sum((p[key]-y[key])**2 for p,y in old)/len(old)
        v7_loss = sum((p[key]-y[key])**2 for p,y in new)/len(new)
        print(f'  {key}: V6={v6_loss:.4f} | V7={v7_loss:.4f}')
    if high < 0:
        print('V7 shows lower Brier in this match-bootstrap interval.')
    elif low > 0:
        print('V6 shows lower Brier in this match-bootstrap interval.')
    else:
        print('Interval includes zero; improvement is not established.')


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected and selected not in LEAGUES:
        raise SystemExit('Usage: python backtest_v71.py [PL|PD|SA|BL1|FL1]')
    failures = []
    codes = [selected] if selected else list(LEAGUES)
    for i, code in enumerate(codes):
        if i:
            time.sleep(7)
        try:
            run_league(code)
        except (RuntimeError, ValueError) as exc:
            print(f'{code}: ERROR {exc}', flush=True)
            failures.append(code)
    print('\nBootstrap treats matches as independent; shared teams and time dependence '
          'can make intervals too narrow. This is exploratory, not a profit guarantee.')
    print('Both models tuned on 2024 only; 2025 used for comparison only.')
    if failures:
        raise SystemExit('Incomplete leagues: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
