"""AVAX FUTBOL ANALIZ PRO V8.2 - Live Engine.

Supports five domestic leagues and Champions League.

Uses chronological match histories and
pre-kickoff opponent-strength snapshots.

Experimental probabilities, not guaranteed outcomes.
"""

from collections import defaultdict
from datetime import datetime, timezone

from backtest_v6 import expected as v6_expected
from backtest_v6 import probabilities, valid
from backtest_v7 import CONFIGS, estimate as v7_estimate
from v8_models import get_league_models

LEAGUES = ("PL", "PD", "SA", "BL1", "FL1", "CL")

MARKET_KEYS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}


def parse_date(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Mac tarihi eksik")

    dt = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if dt.tzinfo is None:
        raise ValueError("Saat dilimi eksik")

    return dt.astimezone(timezone.utc)


def mean(rows, field):
    return sum(r[field] for r in rows) / len(rows)


def strength(history, team, field, baseline):
    recent = history[team][-10:]

    if len(recent) < 3:
        return 1.0

    value = mean(recent, field) / max(0.3, baseline)
    return max(0.4, min(2.5, value))


def build_histories(matches, kickoff):
    cutoff = parse_date(kickoff)
    eligible = []

    for match in valid(matches):
        match_time = parse_date(match["utcDate"])

        if match_time < cutoff:
            eligible.append((match_time, match))

    eligible.sort(
        key=lambda item: (
            item[0],
            item[1]["id"],
        )
    )

    h6 = defaultdict(list)
    h7 = defaultdict(list)

    total_home = 0
    total_away = 0
    games = 0
    pos = 0

    while pos < len(eligible):
        end = pos + 1
        current_time = eligible[pos][0]

        while (
            end < len(eligible)
            and eligible[end][0] == current_time
        ):
            end += 1

        league_home = (
            total_home / games if games >= 10 else 1.4
        )
        league_away = (
            total_away / games if games >= 10 else 1.1
        )

        updates = []

        for _, match in eligible[pos:end]:
            hid = match["homeTeam"]["id"]
            aid = match["awayTeam"]["id"]

            hg = match["score"]["fullTime"]["home"]
            ag = match["score"]["fullTime"]["away"]

            s6 = (
                strength(h6, aid, 2, 1.4),
                strength(h6, aid, 1, 1.4),
                strength(h6, hid, 2, 1.4),
                strength(h6, hid, 1, 1.4),
            )

            s7 = (
                strength(h7, aid, 2, league_away),
                strength(h7, aid, 1, league_home),
                strength(h7, hid, 2, league_away),
                strength(h7, hid, 1, league_home),
            )

            updates.append(
                (hid, aid, hg, ag, s6, s7)
            )

        for hid, aid, hg, ag, s6, s7 in updates:
            for history, snapshot in (
                (h6, s6),
                (h7, s7),
            ):
                ad, aa, hd, ha = snapshot

                history[hid].append(
                    ("home", hg, ag, ad, aa)
                )
                history[aid].append(
                    ("away", ag, hg, hd, ha)
                )

            total_home += hg
            total_away += ag
            games += 1

        pos = end

    league_home = (
        total_home / games if games >= 10 else 1.4
    )
    league_away = (
        total_away / games if games >= 10 else 1.1
    )

    return h6, h7, league_home, league_away, games


def predict(league, home_id, away_id, kickoff, matches):
    league = str(league).upper()

    if league not in LEAGUES:
        raise ValueError("Desteklenmeyen lig")

    home_id = int(home_id)
    away_id = int(away_id)

    if home_id == away_id:
        raise ValueError("Takimlar farkli olmali")

    h6, h7, league_home, league_away, games = (
        build_histories(matches, kickoff)
    )

    if (
        len(h6[home_id]) < 3
        or len(h6[away_id]) < 3
    ):
        raise ValueError(
            "Yeterli gecmis mac verisi yok"
        )

    selections = get_league_models(league)

    output = {}
    models = {}

    for market, model in selections.items():
        if market not in MARKET_KEYS:
            raise ValueError("Bilinmeyen market")

        if model.startswith("V6_"):
            blend = float(model.split("_")[1])

            goals = v6_expected(
                h6, home_id, away_id, blend
            )

        elif model.startswith("V7_"):
            index = int(model.split("_")[1])

            if index < 0 or index >= len(CONFIGS):
                raise ValueError("Gecersiz V7 modeli")

            goals = v7_estimate(
                h7,
                home_id,
                away_id,
                league_home,
                league_away,
                CONFIGS[index],
            )

        else:
            raise ValueError("Bilinmeyen model")

        if goals is None:
            raise ValueError(
                "Tahmin icin yeterli veri yok"
            )

        values = probabilities(*goals)

        for key in MARKET_KEYS[market]:
            output[key] = round(
                100 * max(0.0, min(1.0, values[key])),
                2,
            )

        models[market] = {
            "model": model,
            "expected_home_goals": round(goals[0], 3),
            "expected_away_goals": round(goals[1], 3),
        }

    output["under25"] = round(
        100 - output["over25"], 2
    )
    output["no_btts"] = round(
        100 - output["btts"], 2
    )

    return {
        "league": league,
        "home_id": home_id,
        "away_id": away_id,
        "kickoff": kickoff,
        "matches_in_history": games,
        "probabilities_percent": output,
        "models": models,
        "warning": (
            "Deneysel tahmin. Canli veri ve "
            "kalibrasyon testleri gereklidir."
        ),
    }
