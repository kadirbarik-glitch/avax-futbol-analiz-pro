"""League discovery and prediction eligibility for V8.3.

Discovery only describes API access. A discovered competition never receives
a prediction model automatically.
"""

from v8_models import MODEL_SELECTIONS


TURKEY_CODES = {"TUR", "TR"}
TURKEY_NAMES = {"turkey", "türkiye"}
VALIDATED_NAMES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "CL": "UEFA Champions League",
}


def is_turkey_competition(item):
    area = item.get("area") or {}
    area_code = str(
        area.get("code") or area.get("countryCode") or ""
    ).upper()
    area_name = str(area.get("name") or "").casefold()
    name = str(item.get("name") or "").casefold()

    return (
        area_code in TURKEY_CODES
        or area_name in TURKEY_NAMES
        or "süper lig" in name
        or "super lig" in name
    )


def model_capability(code):
    if code in MODEL_SELECTIONS:
        return (
            "VALIDATED",
            "Bu lig icin V8.3 modeli dogrulandi.",
        )

    return (
        "RESEARCH_REQUIRED",
        "Bu lig bulundu; tahmin icin ayri model "
        "dogrulamasi gerekiyor.",
    )


def normalize_competition(item):
    if not isinstance(item, dict):
        return None

    code = str(item.get("code") or "").upper().strip()
    name = str(item.get("name") or "").strip()

    if not code or not name:
        return None

    model_status, model_message = model_capability(code)
    area = item.get("area") or {}

    return {
        "code": code,
        "name": name,
        "area": str(area.get("name") or ""),
        "turkey_priority": is_turkey_competition(item),
        "access_status": "ACCESSIBLE",
        "access_message": "Mevcut API aboneliginde erisilebilir.",
        "model_status": model_status,
        "model_message": model_message,
        "data_status": "NOT_CHECKED",
        "data_message": (
            "Veri kapsami, secildiginde ayri kontrol edilir."
        ),
        "prediction_allowed": model_status == "VALIDATED",
    }


def fallback_catalog(message):
    entries = []

    for code in MODEL_SELECTIONS:
        model_status, model_message = model_capability(code)
        entries.append({
            "code": code,
            "name": VALIDATED_NAMES.get(code, code),
            "area": "",
            "turkey_priority": False,
            "access_status": "CATALOG_UNAVAILABLE",
            "access_message": message,
            "model_status": model_status,
            "model_message": model_message,
            "data_status": "NOT_CHECKED",
            "data_message": "Lig katalogu olmadan veri kontrolu yapilamaz.",
            "prediction_allowed": False,
        })

    return entries


def discover_catalog(payload, error=None):
    """Return accessible competitions, prioritising Turkey without guessing IDs."""

    if error or not isinstance(payload, dict):
        return fallback_catalog(
            error or "Lig katalogu su anda alinamiyor."
        )

    competitions = payload.get("competitions")
    if not isinstance(competitions, list):
        return fallback_catalog("Lig katalogu gecersiz yanit verdi.")

    entries = []
    seen = set()

    for item in competitions:
        entry = normalize_competition(item)
        if entry and entry["code"] not in seen:
            entries.append(entry)
            seen.add(entry["code"])

    entries.sort(
        key=lambda entry: (
            not entry["turkey_priority"],
            entry["model_status"] != "VALIDATED",
            entry["name"].casefold(),
            entry["code"],
        )
    )
    return entries


def selected_capability(catalog, code):
    code = str(code or "").upper()

    for entry in catalog:
        if entry["code"] == code:
            return entry

    return {
        "code": code,
        "name": code or "Bilinmeyen lig",
        "area": "",
        "turkey_priority": False,
        "access_status": "NOT_ACCESSIBLE",
        "access_message": (
            "Bu lig mevcut API aboneliginde listelenmiyor."
        ),
        "model_status": "RESEARCH_REQUIRED",
        "model_message": "Dogrulanmis model kaydi bulunmuyor.",
        "data_status": "NOT_CHECKED",
        "data_message": "Erisim olmadigi icin veri kontrolu yapilamadi.",
        "prediction_allowed": False,
    }


def with_data_status(capability, readiness):
    output = capability.copy()
    output.update({
        "data_status": readiness["status"],
        "data_message": readiness["message"],
        "historical_matches": readiness.get("matches"),
    })
    return output
