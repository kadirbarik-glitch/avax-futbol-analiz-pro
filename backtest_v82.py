
"""AVAX V8.2 - Sampiyonlar Ligi veri arastirmasi.

Sezonlar: 2023, 2024, 2025
API kodu: CL

Bu ilk asama veri kalitesini inceler.
Henuz tahmin modeli secmez veya bahis onermez.

Calistirma:
    python backtest_v82.py
"""

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
from pathlib import Path
import json
import os
import time

from backtest_v6 import fetch, valid

CODE = "CL"
SEASONS = ("2023", "2024", "2025")
CACHE_DIR = Path("data_cache")
REQUEST_INTERVAL = 7
MIN_TEAM_MATCHES = 3
MANIFEST_NAME = "CL_manifest.json"


def load_season(season, allow_download):
    """Load validated cache; download only when explicitly allowed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{CODE}_{season}.json"

    if path.exists():
        try:
            with path.open(encoding="utf-8") as f:
                raw = json.load(f)

            matches = valid(raw) if isinstance(raw, list) else []

            if not matches:
                raise ValueError("Gecersiz onbellek")

            print(f"{season}: CACHE HIT", flush=True)
            return matches, False

        except (OSError, ValueError, TypeError, KeyError):
            print(
                f"{season}: Onbellek gecersiz, "
                "yeniden indirilecek",
                flush=True,
            )

    if not allow_download:
        raise RuntimeError(
            f"Eksik veya gecersiz cache: {path}. "
            "Indirmek icin --download kullanin."
        )

    if not os.getenv("FOOTBALL_DATA_API_KEY"):
        raise RuntimeError(
            "FOOTBALL_DATA_API_KEY gerekli"
        )

    raw = fetch(CODE, season)
    matches = valid(raw)

    if not matches:
        raise ValueError(f"API gecerli mac dondurmedi: {season}")

    temporary = path.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as f:
        json.dump(raw, f)

    temporary.replace(path)

    print(
        f"{season}: API verisi indirildi",
        flush=True,
    )

    return matches, True


def write_manifest():
    """Record cache provenance without storing credentials."""

    seasons = {}

    for season in SEASONS:
        path = CACHE_DIR / f"{CODE}_{season}.json"
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes)
        matches = valid(raw) if isinstance(raw, list) else []

        if not matches:
            raise ValueError(
                f"Manifest icin gecersiz cache: {path}"
            )

        seasons[season] = {
            "file": path.name,
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "raw_matches": len(raw),
            "valid_matches": len(matches),
        }

    manifest = {
        "schema_version": 1,
        "competition": CODE,
        "source": "football-data.org/v4",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "seasons": seasons,
    }

    temporary = CACHE_DIR / f"{MANIFEST_NAME}.tmp"
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(CACHE_DIR / MANIFEST_NAME)


def inspect_season(season, matches):
    """Takim ve mac verilerinin kalitesini olc."""

    teams = Counter()
    home_goals = 0
    away_goals = 0
    unique_ids = set()
    valid_dates = 0

    for match in matches:
        mid = match["id"]
        unique_ids.add(mid)

        home = match["homeTeam"]["id"]
        away = match["awayTeam"]["id"]

        teams[home] += 1
        teams[away] += 1

        score = match["score"]["fullTime"]
        home_goals += score["home"]
        away_goals += score["away"]

        try:
            date = datetime.fromisoformat(
                match["utcDate"].replace(
                    "Z", "+00:00"
                )
            )
            if date.tzinfo is not None:
                valid_dates += 1
        except (ValueError, TypeError):
            pass

    count = len(matches)

    print("\n" + "=" * 45)
    print("AVAX V8.2 - CHAMPIONS LEAGUE")
    print("Sezon:", season)
    print("Tamamlanmis mac:", count)
    print("Takim sayisi:", len(teams))
    print("Benzersiz mac ID:", len(unique_ids))
    print("Gecerli tarih:", valid_dates)

    if count == 0:
        print("SONUC: Veri bulunamadi")
        return

    print(
        "Ev sahibi gol ortalamasi:",
        round(home_goals / count, 3),
    )
    print(
        "Deplasman gol ortalamasi:",
        round(away_goals / count, 3),
    )

    enough = sum(
        games >= MIN_TEAM_MATCHES
        for games in teams.values()
    )

    print(
        "En az 3 maci olan takim:",
        enough,
        "/", len(teams),
    )

    print(
        "Takim basi minimum mac:",
        min(teams.values()),
    )
    print(
        "Takim basi maksimum mac:",
        max(teams.values()),
    )

    # Fikstur tarihine kadar yeterli gecmis
    # maci olan takimlarin oranini hesapla.
    history = Counter()
    eligible = 0
    pos = 0

    while pos < count:
        end = pos + 1

        while (
            end < count
            and matches[end]["utcDate"]
            == matches[pos]["utcDate"]
        ):
            end += 1

        batch = matches[pos:end]

        for match in batch:
            home = match["homeTeam"]["id"]
            away = match["awayTeam"]["id"]

            if (
                history[home] >= MIN_TEAM_MATCHES
                and history[away] >= MIN_TEAM_MATCHES
            ):
                eligible += 1

        # Ayni saatteki maclar bitmeden
        # digerinin sonucunu kullanma.
        for match in batch:
            history[match["homeTeam"]["id"]] += 1
            history[match["awayTeam"]["id"]] += 1

        pos = end

    print(
        "Gecmise dayali tahmine uygun mac:",
        eligible,
        "/", count,
    )

    print(
        "Uygunluk orani:",
        f"{eligible / count:.1%}",
    )

    if eligible < 50:
        print(
            "UYARI: Model testi icin "
            "ornegin kapsami dusuk."
        )
    else:
        print(
            "Veri kapsami model testine "
            "aday gorunuyor."
        )

    print(
        "NOT: Veri kapsami tahmin "
        "dogrulugu anlamina gelmez."
    )


def main():
    parser = argparse.ArgumentParser(
        description="CL cache research; downloads require --download."
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Eksik veya gecersiz sezonlari API'den indir.",
    )
    args = parser.parse_args()

    print("AVAX V8.2 - Veri kalite arastirmasi")
    print("Lig: UEFA Champions League")
    print("Sezonlar:", ", ".join(SEASONS))

    failures = []
    last_request = False

    for season in SEASONS:
        try:
            cache_path = (
                CACHE_DIR / f"{CODE}_{season}.json"
            )

            if (
                not cache_path.exists()
                and last_request
            ):
                time.sleep(REQUEST_INTERVAL)

            matches, downloaded = load_season(
                season, args.download
            )

            last_request = downloaded

            inspect_season(season, matches)

        except (
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
            OSError,
        ) as exc:
            failures.append(season)
            print(
                f"{season}: VERI HATASI: {exc}",
                flush=True,
            )

    print("\n" + "=" * 45)
    print("AVAX V8.2 arastirma tamamlandi.")

    if failures:
        print(
            "Eksik sezonlar:",
            ", ".join(failures),
        )
        raise SystemExit(1)

    write_manifest()
    print(
        f"Manifest yazildi: {CACHE_DIR / MANIFEST_NAME}"
    )

    print(
        "Sonraki asama: V6/V7 model "
        "karsilastirmasi."
    )
    print(
        "Gecmis veri testi, gelecekte "
        "kazanc garantisi vermez."
    )


if __name__ == "__main__":
    main()
