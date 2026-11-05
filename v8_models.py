"""AVAX FUTBOL ANALIZ PRO V8.2
League and market-specific model selections.

Champions League:
2023 model selection
2024 validation
2025 historical evaluation

Experimental models. No guaranteed accuracy.
"""

MODEL_SELECTIONS = {
    "PL": {
        "match_result": "V6_0.75",
        "over25": "V7_02",
        "btts": "V7_02",
    },
    "PD": {
        "match_result": "V6_0.50",
        "over25": "V7_03",
        "btts": "V7_03",
    },
    "SA": {
        "match_result": "V6_0.25",
        "over25": "V7_03",
        "btts": "V7_04",
    },
    "BL1": {
        "match_result": "V6_0.25",
        "over25": "V6_1.00",
        "btts": "V6_0.75",
    },
    "FL1": {
        "match_result": "V7_17",
        "over25": "V7_02",
        "btts": "V7_02",
    },
    "CL": {
        "match_result": "V7_15",
        "over25": "V7_03",
        "btts": "V7_17",
    },
}

MARKETS = ("match_result", "over25", "btts")


def get_model(league, market):
    league = str(league).upper()

    if league not in MODEL_SELECTIONS:
        raise ValueError(
            f"Desteklenmeyen lig: {league}"
        )

    if market not in MARKETS:
        raise ValueError(
            f"Desteklenmeyen bahis turu: {market}"
        )

    return MODEL_SELECTIONS[league][market]


def get_league_models(league):
    league = str(league).upper()

    if league not in MODEL_SELECTIONS:
        raise ValueError(
            f"Desteklenmeyen lig: {league}"
        )

    return MODEL_SELECTIONS[league].copy()


if __name__ == "__main__":
    for league in MODEL_SELECTIONS:
        print(league, get_league_models(league))
