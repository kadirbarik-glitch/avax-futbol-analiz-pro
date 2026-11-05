"""AVAX V3.5: train on 2024, holdout-test on 2025 across five leagues.

Requires FOOTBALL_DATA_API_KEY. Run: python backtest_v5.py [PL|PD|SA|BL1|FL1]
The historical predictor uses only earlier matches in the SAME season.
2024 determines a shrinkage weight; 2025 is held out for evaluation.
"""
import os
import sys
import time
from backtest_v4 import LEAGUES, MARKETS, fetch, evaluate, valid_matches

TRAIN = '2024'
TEST = '2025'
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)


def metrics(rows, key, weight=1.0, prior=0.5):
    n = len(rows)
    if not n:
        raise ValueError('No evaluated matches')
    return sum((weight * p[key] + (1.0 - weight) * prior - y[key]) ** 2
               for p, y in rows) / n


def fit(train_rows):
    n = len(train_rows)
    priors = {key: sum(y[key] for _, y in train_rows) / n for key, _ in MARKETS}
    weights = {}
    for key, _ in MARKETS:
        weights[key] = min(WEIGHTS, key=lambda w: metrics(train_rows, key, w, priors[key]))
    # Apply one common shrinkage weight to the three mutually exclusive outcomes.
    # This keeps their probabilities summing to approximately 1.
    outcome = ('home', 'draw', 'away')
    common = min(WEIGHTS, key=lambda w: sum(metrics(train_rows, k, w, priors[k]) for k in outcome))
    for key in outcome:
        weights[key] = common
    return priors, weights


def report(code, train_rows, test_rows):
    if len(train_rows) < 50 or len(test_rows) < 50:
        print(f'{code}: INSUFFICIENT DATA: train={len(train_rows)}, test={len(test_rows)}')
        return False
    priors, weights = fit(train_rows)
    print(f'\n{LEAGUES[code]} | training {TRAIN}: {len(train_rows)} | holdout {TEST}: {len(test_rows)}')
    for key, label in MARKETS:
        raw = metrics(test_rows, key)
        calibrated = metrics(test_rows, key, weights[key], priors[key])
        baseline = metrics(test_rows, key, 0.0, priors[key])
        print(f'{label}: raw Brier={raw:.4f} | adjusted={calibrated:.4f} | '
              f'train-only baseline={baseline:.4f} | weight={weights[key]:.2f}')
    raw_correct = sum(max(('home', 'draw', 'away'), key=lambda k: p[k]) ==
                      ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                      for p, y in test_rows)
    adjusted_correct = sum(max(('home', 'draw', 'away'),
                               key=lambda k: weights[k] * p[k] + (1 - weights[k]) * priors[k]) ==
                           ('home' if y['home'] else 'draw' if y['draw'] else 'away')
                           for p, y in test_rows)
    print(f'Match outcome accuracy: raw={raw_correct/len(test_rows):.1%}, '
          f'adjusted={adjusted_correct/len(test_rows):.1%}')
    return True


def main():
    if not os.environ.get('FOOTBALL_DATA_API_KEY', '').strip():
        raise SystemExit('FOOTBALL_DATA_API_KEY missing')
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected and selected not in LEAGUES:
        raise SystemExit('Usage: python backtest_v5.py [PL|PD|SA|BL1|FL1]')
    codes = [selected] if selected else list(LEAGUES)
    failures = []
    for i, code in enumerate(codes):
        try:
            season_rows = {}
            for season in (TRAIN, TEST):
                if i or season != TRAIN:
                    time.sleep(7)
                data = fetch(f'/competitions/{code}/matches?season={season}&status=FINISHED')
                season_rows[season] = evaluate(valid_matches(data))
            if not report(code, season_rows[TRAIN], season_rows[TEST]):
                failures.append(code)
        except RuntimeError as exc:
            print(f'{code}: API ERROR: {exc}', flush=True)
            failures.append(code)
    print('\n2025 is holdout data, not used to select weights or baselines.')
    print('2024 training metrics are in-sample; use additional seasons for stronger evidence.')
    print('Historical evaluation is not a guarantee of future accuracy or profit.')
    if failures:
        raise SystemExit('Incomplete leagues: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
