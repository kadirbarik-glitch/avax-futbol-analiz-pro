import os
from flask import Flask, request, session, redirect, render_template_string
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

@app.route("/", methods=["GET", "POST"])
def giris():
    hata = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        sifre = request.form.get("sifre", "")

        kayitli_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        kayitli_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()

        if email == kayitli_email and check_password_hash(kayitli_hash, sifre):
            session.clear()
            session["giris"] = True
            return redirect("/panel")

        hata = "Giriş bilgileri hatalı."

    return render_template_string("""
    <html lang="tr">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <body style="font-family:Arial;max-width:400px;margin:60px auto;padding:20px">
    <h2>AVAX FUTBOL ANALİZ PRO</h2>
    <p style="color:red">{{ hata }}</p>
    <form method="post">
      <input name="email" type="email" placeholder="E-posta" required>
      <p><input name="sifre" type="password" placeholder="Şifre" required></p>
      <button type="submit">Giriş Yap</button>
    </form>
    </body></html>
    """, hata=hata), (401 if hata else 200)

@app.route("/panel")
def panel():
    if not session.get("giris"):
        return redirect("/")
    return "<h2>AVAX FUTBOL ANALİZ PRO</h2><p>Özel panel hazır.</p><a href='/cikis'>Çıkış Yap</a>"

@app.route("/cikis")
def cikis():
    session.clear()
    return redirect("/")
