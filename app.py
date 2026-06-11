import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from dotenv import load_dotenv
import requests

# Charger les variables d'environnement au début
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialisation de Supabase à l'intérieur des fonctions ou avec une fonction factory
def init_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise ValueError("Les variables d'environnement SUPABASE_URL et SUPABASE_ANON_KEY doivent être définies")
    return create_client(url, key)

def init_supabase_admin():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("La variable d'environnement SUPABASE_SERVICE_KEY doit être définie")
    return create_client(url, key)

# Fonctions d'accès à la base de données avec initialisation tardive
def get_supabase():
    if not hasattr(app, 'supabase_client'):
        app.supabase_client = init_supabase()
    return app.supabase_client

def get_supabase_admin():
    if not hasattr(app, 'supabase_admin_client'):
        app.supabase_admin_client = init_supabase_admin()
    return app.supabase_admin_client

def get_all_candidats():
    supabase = get_supabase()
    response = supabase.table("candidats").select("*").order("created_at", desc=True).execute()
    return response.data

def get_candidat_by_id(candidat_id):
    supabase = get_supabase()
    response = supabase.table("candidats").select("*").eq("id", candidat_id).execute()
    return response.data[0] if response.data else None

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    candidats = get_all_candidats()
    return render_template("index.html", candidats=candidats)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            supabase_url = os.environ.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_ANON_KEY")
            url = f"{supabase_url}/auth/v1/token?grant_type=password"
            payload = {"email": email, "password": password}
            headers = {"apikey": supabase_key, "Content-Type": "application/json"}
            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                session["user"] = resp.json()["user"]
                return redirect(url_for("index"))
            else:
                flash("Identifiants incorrects")
        except Exception as e:
            flash(f"Erreur : {e}")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/add", methods=["GET", "POST"])
def add_candidat():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        nom = request.form["nom"]
        telephone = request.form["telephone"]
        phase = request.form["phase"]
        tarif = float(request.form["tarif"])
        versement = float(request.form["versement"])
        photo_url = None
        
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file_bytes = file.read()
                if len(file_bytes) > 5_000_000:
                    flash("La photo ne doit pas dépasser 5 Mo.")
                    return redirect(url_for("add_candidat"))
                supabase_admin = get_supabase_admin()
                supabase_admin.storage.from_("photos_candidats").upload(
                    filename,
                    file_bytes,
                    {"content-type": file.mimetype or "image/jpeg"}
                )
                photo_url = supabase_admin.storage.from_("photos_candidats").get_public_url(filename)
        
        data = {
            "nom": nom,
            "telephone": telephone,
            "phase": phase,
            "tarif": tarif,
            "versement": versement,
            "photo_url": photo_url,
        }
        supabase = get_supabase()
        supabase.table("candidats").insert(data).execute()
        flash("Candidat ajouté")
        return redirect(url_for("index"))
    return render_template("add_candidat.html")

@app.route("/candidat/<candidat_id>")
def candidat_detail(candidat_id):
    if "user" not in session:
        return redirect(url_for("login"))
    candidat = get_candidat_by_id(candidat_id)
    if not candidat:
        flash("Candidat introuvable")
        return redirect(url_for("index"))
    return render_template("candidat_detail.html", c=candidat)

@app.route("/edit/<candidat_id>", methods=["GET", "POST"])
def edit_candidat(candidat_id):
    if "user" not in session:
        return redirect(url_for("login"))
    candidat = get_candidat_by_id(candidat_id)
    if not candidat:
        flash("Candidat introuvable")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        nom = request.form["nom"]
        telephone = request.form["telephone"]
        phase = request.form["phase"]
        tarif = float(request.form["tarif"])
        versement = float(request.form["versement"])
        photo_url = candidat["photo_url"]
        
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file_bytes = file.read()
                if len(file_bytes) > 5_000_000:
                    flash("La photo ne doit pas dépasser 5 Mo.")
                    return redirect(url_for("edit_candidat", candidat_id=candidat_id))
                supabase_admin = get_supabase_admin()
                supabase_admin.storage.from_("photos_candidats").upload(
                    filename,
                    file_bytes,
                    {"content-type": file.mimetype or "image/jpeg"}
                )
                photo_url = supabase_admin.storage.from_("photos_candidats").get_public_url(filename)
        
        data = {
            "nom": nom,
            "telephone": telephone,
            "phase": phase,
            "tarif": tarif,
            "versement": versement,
            "photo_url": photo_url,
            "updated_at": datetime.now().isoformat(),
        }
        supabase = get_supabase()
        supabase.table("candidats").update(data).eq("id", candidat_id).execute()
        flash("Modifié")
        return redirect(url_for("candidat_detail", candidat_id=candidat_id))
    
    return render_template("add_candidat.html", candidat=candidat)

@app.route("/delete/<candidat_id>")
def delete_candidat(candidat_id):
    if "user" not in session:
        return redirect(url_for("login"))
    supabase = get_supabase()
    supabase.table("candidats").delete().eq("id", candidat_id).execute()
    flash("Supprimé")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))