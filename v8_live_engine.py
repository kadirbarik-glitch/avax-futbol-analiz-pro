
"""AVAX V8 - Gunluk mac tahmin motoru.

V6/V7 tarihsel hesaplama yontemlerini kullanir.
Yalnizca mac baslangicindan onceki veriler kullanilir.
Tahminler garanti veya kalibre edilmis guven degildir.
"""

from collections import defaultdict
from datetime import datetime, timezone

from backtest_v6 import expected as v6_expected
from backtest_v6 import probabilities, valid
from backtest_v7 import CONFIGS, estimate as v7_estimate
from v8_models import get_league_models

LEAGUE_CODES = ("PL", "PD", "SA", "BL1", "FL1")
MARKET_KEYS = {
    "match_result": ("home", "draw", "away"),
    "over25": ("over25",),
    "btts": ("btts",),
}


def _average(rows, field):
    return sum(row[field] for row in rows) / len(rows)


def _strength(history, team_id, field, baseline):
    recent = history[team_id][-10:]
    if len(recent) < 3:
        return 1.0
    value = _average(recent, field) / max(0.3, baseline)
    return max(0.4, min(2.5, value))


def _parse_date(value):
    if not value:
        raise ValueError("Mac tarihi eksik")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_histories(matches, kickoff):
    """Sadece baslangictan onceki bitmis maclari isle."""
    cutoff = _parse_date(kickoff)

    eligible = [
        m for m in valid(matches)
        if _parse_date(m["utcDate"]) < cutoff
    ]

    h6 = defaultdict(list)
    h7 = defaultdict(list)
    league_home_goals = 0
    league_away_goals = 0
    league_games = 0

    pos = 0
    while pos < len(eligible):
        end = pos + 1
        while (
            end < len(eligible)
            and eligible[end]["utcDate"] == eligible[pos]["utcDate"]
        ):
            end += 1

        league_h = (
            league_home_goals / league_games
            if league_games >= 10 else 1.4
        )
        league_a = (
            league_away_goals / league_games
            if league_games >= 10 else 1.1
        )

        updates = []

        for m in eligible[pos:end]:
            hid = m["homeTeam"]["id"]
            aid = m["awayTeam"]["id"]
            hg = m["score"]["fullTime"]["home"]
            ag = m["score"]["fullTime"]["away"]

            # V6'nin tarihsel rakip gucu hesabi
            v6_ad = _strength(h6, aid, 2, 1.4)
            v6_aa = _strength(h6, aid, 1, 1.4)
            v6_hd = _strength(h6, hid, 2, 1.4)
            v6_ha = _strength(h6, hid, 1, 1.4)

            # V7'nin lig ortalamali rakip gucu hesabi
            v7_ad = _strength(h7, aid, 2, league_a)
            v7_aa = _strength(h7, aid, 1, league_h)
            v7_hd = _strength(h7, hid, 2, league_a)
            v7_ha = _strength(h7, hid, 1, league_h)

            updates.append((
                hid, aid, hg, ag,
                (v6_ad, v6_aa, v6_hd, v6_ha),
                (v7_ad, v7_aa, v7_hd, v7_ha),
            ))

        # Ayni saatte baslayan maclar birlikte guncellenir.
        for hid, aid, hg, ag, s6, s7 in updates:
            for history, strengths in ((h6, s6), (h7, s7)):
                ad, aa, hd, ha = strengths
                history[hid].append(
                    ("home", hg, ag, ad, aa)
                )
                history[aid].append(
                    ("away", ag, hg, hd, ha)
                )

            league_home_goals += hg
            league_away_goals += ag
            league_games += 1

        pos = end

    league_h = (
        league_home_goals / league_games
        if league_games >= 10 else 1.4
    )
    league_a = (
        league_away_goals / league_games
        if league_games >= 10 else 1.1
    )

    return h6, h7, league_h, league_a, league_games


def predict(league, home_id, away_id, kickoff, matches):
    """Secilen modellerle uc marketin olasiligini hesapla."""
    league = str(league).upper()

    if league not in LEAGUE_CODES:
        raise ValueError("Desteklenmeyen lig")

    home_id = int(home_id)
    away_id = int(away_id)

    if home_id == away_id:
        raise ValueError("Takimlar farkli olmali")

    h6, h7, league_h, league_a, n = build_histories(
        matches, kickoff
    )

    if len(h6[home_id]) < 3 or len(h6[away_id]) < 3:
        raise ValueError(
            "Bu sezon yeterli takim mac verisi bulunamadi"
        )

    selected = get_league_models(league)
    output = {}
    used = {}

    for market, model_name in selected.items():
        if model_name.startswith("V6_"):
            blend = float(model_name.split("_")[1])
            goals = v6_expected(
                h6, home_id, away_id, blend
            )

        elif model_name.startswith("V7_"):
            index = int(model_name.split("_")[1])
            if not 0 <= index < len(CONFIGS):
                raise ValueError("Gecersiz V7 modeli")

            goals = v7_estimate(
                h7, home_id, away_id,
                league_h, league_a, CONFIGS[index]
            )

        else:
            raise ValueError("Bilinmeyen model")

        if goals is None:
            raise ValueError("Tahmin icin veri yetersiz")

        values = probabilities(*goals)
        for key in MARKET_KEYS[market]:
            output[key] = round(
                max(0.0, min(1.0, values[key])) * 100, 2
            )

        used[market] = {
            "model": model_name,
            "expected_home_goals": round(goals[0], 3),
            "expected_away_goals": round(goals[1], 3),
        }

    output["under25"] = round(100 - output["over25"], 2)
    output["no_btts"] = round(100 - output["btts"], 2)

    return {
        "league": league,
        "home_id": home_id,
        "away_id": away_id,
        "kickoff": kickoff,
        "matches_in_history": n,
        "probabilities_percent": output,
        "models": used,
        "warning": (
            "Deneysel olasiliklar. Kalibrasyon ve "
            "canli veri dogrulamasi gereklidir."
        ),
    }
