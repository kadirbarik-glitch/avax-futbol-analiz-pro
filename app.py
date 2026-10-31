from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def ana_sayfa():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>AVAX FUTBOL ANALİZ PRO</title>
    </head>
    <body style="background:#101827;color:white;
                 font-family:Arial;text-align:center;
                 padding:40px 15px;">
        <h1>⚽ AVAX FUTBOL ANALİZ PRO</h1>
        <h2>Futbol Analiz Merkezi</h2>
        <p>Program başarıyla çalışıyor.</p>
        <p>Maç analiz sistemi hazırlanıyor.</p>
    </body>
    </html>
    """)
