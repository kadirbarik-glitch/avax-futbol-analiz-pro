"""AVAX V7: league-aware, recency-weighted opponent-strength backtest.
Usage: python backtest_v7.py [PL|PD|SA|BL1|FL1]
2024 selects configuration; 2025 is held out. Requires FOOTBALL_DATA_API_KEY.
This is an experimental research script, not a betting recommendation.
"""
import sys
import time
from collections import defaultdict
from backtest_v6 import LEAGUES, MARKETS, fetch, valid, probabilities, evaluate as v6_evaluate

TRAIN, TEST = '2024', '2025'
CONFIGS = [(recency, shrink, blend) for recency in (0.0, 0.08)
           for shrink in (0.25, 0.5, 0.75) for blend in (0.0, 0.5, 1.0)]

def weighted_avg(items, field, recency):
    weights = [(1 + recency) ** i for i in range(len(items))]
    return sum(w * row[field] for w, row in zip(weights, items)) / sum(weights)

def estimate(history, hid, aid, league_home, league_away, config):
    recency, shrink, blend = config
    hh, aa = history[hid][-20:], history[aid][-20:]
    if len(hh) < 3 or len(aa) < 3:
        return None
    home = [r for r in hh if r[0] == 'home']
    away = [r for r in aa if r[0] == 'away']
    home = home if len(home) >= 3 else hh[-10:]
    away = away if len(away) >= 3 else aa[-10:]

    def rate(rows, field):
        simple = weighted_avg(rows, field, recency)
        # Opponent-strength snapshots are saved BEFORE each prior match.
        strength_index = 3 if field == 1 else 4
        adjusted = weighted_avg(
            [(r[0], r[field] / max(.4, min(2.5, r[strength_index]))) for r in rows],
            1, recency)
        return (1 - blend) * simple + blend * adjusted

    raw_h = (rate(home, 1) + rate(away, 2)) / 2
    raw_a = (rate(away, 1) + rate(home, 2)) / 2
    # Shrink unstable team estimates toward league-specific pre-kickoff means.
    reliability = min(1.0, min(len(home), len(away)) / 8.0)
    effective = shrink * reliability
    h = effective * raw_h + (1 - effective) * league_home
    a = effective * raw_a + (1 - effective) * league_away
    return min(8, max(.05, h)), min(8, max(.05, a))

def evaluate_v7(matches, config):
    history = defaultdict(list)
    rows = []
    league_h_goals = league_a_goals = 0
    league_games = 0
    pos = 0
    while pos < len(matches):
        end = pos + 1
        while end < len(matches) and matches[end]['utcDate'] == matches[pos]['utcDate']:
            end += 1
        batch = matches[pos:end]
        # League priors use only results strictly before this kickoff.
        league_home = league_h_goals / league_games if league_games >= 10 else 1.4
        league_away = league_a_goals / league_games if league_games >= 10 else 1.1
        updates = []
        for m in batch:
            hid, aid = m['homeTeam']['id'], m['awayTeam']['id']
            hg, ag = m['score']['fullTime']['home'], m['score']['fullTime']['away']
            ex = estimate(history, hid, aid, league_home, league_away, config)
            if ex is not None:
                p = probabilities(*ex)
                y = {'home': int(hg > ag), 'draw': int(hg == ag),
                     'away': int(hg < ag), 'over25': int(hg + ag >= 3),
                     'btts': int(hg > 0 and ag > 0)}
                rows.append((p, y))
            def strength(team, field):
                recent = history[team][-10:]
                base = league_home if field == 1 else league_away
                return max(.4, min(2.5, weighted_avg(recent, field, 0) / max(.3, base))) if len(recent) >= 3 else 1.0
            updates.append((hid, aid, hg, ag, strength(aid, 2), strength(aid, 1),
                            strength(hid, 2), strength(hid, 1)))
        for hid, aid, hg, ag, ad, aa, hd, ha in updates:
            history[hid].append(('home', hg, ag, ad, aa))
            history[aid].append(('away', ag, hg, hd, ha))
            league_h_goals += hg
            league_a_goals += ag
            league_games += 1
        pos = end
    return rows

def brier(rows):
    if not rows:
        raise ValueError('No eligible matches')
    return sum((p[k] - y[k]) ** 2 for p, y in rows for k in MARKETS) / (len(rows) * len(MARKETS))

def accuracy(rows):
    outcomes = ('home', 'draw', 'away')
    return sum(max(outcomes, key=lambda k: p[k]) == max(outcomes, key=lambda k: y[k])
               for p, y in rows) / len(rows)

def run_league(code):
    train = valid(fetch(code, TRAIN))
    time.sleep(7)
    test = valid(fetch(code, TEST))
    if len(train) < 100 or len(test) < 100:
        raise ValueError('Insufficient season data')
    training = [(brier(evaluate_v7(train, cfg)), cfg) for cfg in CONFIGS]
    _, chosen = min(training)
    old = v6_evaluate(test, 0.0)
    new = evaluate_v7(test, chosen)
    if len(old) != len(new) or len(new) < 50:
        raise ValueError('Inconsistent evaluation coverage')
    print(f'\n{LEAGUES[code]} | train={TRAIN} | holdout={TEST} | evaluated={len(new)}')
    print(f'Selected (recency, shrink, opponent blend)={chosen}')
    print(f'V6 simple Brier={brier(old):.4f}; V7 Brier={brier(new):.4f}')
    print(f'V6 simple accuracy={accuracy(old):.1%}; V7 accuracy={accuracy(new):.1%}')
    for k in MARKETS:
        old_b = sum((p[k]-y[k])**2 for p,y in old)/len(old)
        new_b = sum((p[k]-y[k])**2 for p,y in new)/len(new)
        print(f'  {k}: baseline={old_b:.4f}, V7={new_b:.4f}')
    print('NOTE: baseline is V6 with blend=0, not tuned V6. Compare tuned V6 separately.')

def main():
    code = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if code and code not in LEAGUES:
        raise SystemExit('Usage: python backtest_v7.py [PL|PD|SA|BL1|FL1]')
    failures = []
    for i, league in enumerate([code] if code else LEAGUES):
        if i:
            time.sleep(7)
        try:
            run_league(league)
        except (RuntimeError, ValueError) as exc:
            print(f'{league}: ERROR {exc}', flush=True)
            failures.append(league)
    print('\n2025 was not used to select V7 settings. Historical tests do not guarantee profit.')
    if failures:
        raise SystemExit('Incomplete leagues: ' + ', '.join(failures))

if __name__ == '__main__':
    main()
