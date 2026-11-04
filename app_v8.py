
"""AVAX FUTBOL ANALIZ PRO V8 - Hazirlik Surumu.

Mevcut V3 uygulamasini koruyarak ayri bir V8
uygulama giris noktasi olusturur.

V8 model secimi henuz canli tahminlere bagli degildir.
"""

import os

from flask import Flask
from app_v3 import app as app

V8_VERSION = "8.0-hazirlik"


@app.context_processor
def avax_v8_context():
    return {
        "avax_version": V8_VERSION,
        "avax_v8_live_model": False,
    }


@app.after_request
def avax_v8_headers(response):
    response.headers["X-AVAX-Version"] = V8_VERSION
    return response


@app.get("/v8/status")
def avax_v8_status():
    return {
        "application": "AVAX FUTBOL ANALIZ PRO",
        "version": V8_VERSION,
        "status": "ready",
        "existing_v3_features": True,
        "v8_model_integrated": False,
        "message": (
            "V8 uygulama girisi hazir. "
            "Canli V8 tahmin motoru henuz entegre edilmedi."
        ),
    }


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
    )
