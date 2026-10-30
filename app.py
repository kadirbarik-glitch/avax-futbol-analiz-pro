import os
from flask import Flask, request, session, redirect, render_template_string
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

@app.route("/", methods=["GET", "POST"])
def giris():
    if request.method == "POST":
        email = request.form.get("email", "")
        sifre = request.form.get("sifre", "")
        if (email == os.environ.get("ADMIN_EMAIL")
            and check_password_hash(
                os.environ.get("ADMIN_PASSWORD_HASH", ""), sifre
            )):
            session["giris"] = True
            return redirect("/panel")
        return "Giriş bilgileri hatalı.", 401

    return render_template_string("""
    <h2>AVAX FUTBOL ANALİZ PRO</h2>
    <form method="post">
      <input name="email" type="email"
             placeholder="E-posta" required>
      <input name="sifre" type="password"
             placeholder="Şifre" required>
      <button type="submit">Giriş Yap</button>
    </form>
    """)

@app.route("/panel")
def panel():
    if not session.get("giris"):
        return redirect("/")
    return "<h2>AVAX FUTBOL ANALİZ PRO</h2><p>Özel panel hazır.</p>"

@app.route("/cikis")
def cikis():
    session.clear()
    return redirect("/")
