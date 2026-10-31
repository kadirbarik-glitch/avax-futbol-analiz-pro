import os
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

def maclari_getir():
    anahtar = os.environ.get("FOOTBALL_DATA_API_KEY", "")

    if not anahtar:
        return {"maclar": [], "hata": "Futbol veri anahtarı bulunamadı."}

    adres = "https://api.football-data.org/v4/matches?status=SCHEDULED"
    istek = Request(
        adres,
        headers={"X-Auth-Token": anahtar}
    )

    try:
        with urlopen(istek, timeout=15) as cevap:
            veri = json.load(cevap)

        maclar = []
        for mac in veri.get("matches", []):
            maclar.append({
                "tarih": mac.get("utcDate", ""),
                "ev": mac.get("homeTeam", {}).get("name", ""),
                "ev_id": mac.get("homeTeam", {}).get("id"),
                "deplasman": mac.get("awayTeam", {}).get("name", ""),
                "deplasman_id": mac.get("awayTeam", {}).get("id"),
                "lig": mac.get("competition", {}).get("name", "")
            })

        return {"maclar": maclar, "hata": None}

    except HTTPError as hata:
        return {"maclar": [], "hata": f"Veri servisi hatası: {hata.code}"}
    except (URLError, TimeoutError, ValueError):
        return {"maclar": [], "hata": "Maç verileri şu anda alınamadı."}


def gol_ortalamasi(goller):
    if not goller:
        return None
    return round(sum(goller) / len(goller), 2)

def gecmis_maclari_getir(takim_id):
    anahtar = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    if not anahtar:
        return []

    adres = (
        f"https://api.football-data.org/v4/teams/{takim_id}/matches"
        "?status=FINISHED&limit=10"
    )
    istek = Request(adres, headers={"X-Auth-Token": anahtar})

    try:
        with urlopen(istek, timeout=15) as cevap:
            veri = json.load(cevap)
        return veri.get("matches", [])
    except (HTTPError, URLError, TimeoutError, ValueError):
        return []
    
