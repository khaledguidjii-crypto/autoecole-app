import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client
import requests

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Lire les variables d'environnement
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise Exception("Variables d'environnement SUPABASE_URL et SUPABASE_ANON_KEY manquantes")

# Créer les clients Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Créer automatiquement une session utilisateur (pas besoin de login)
@app.before_request
def auto_login():
    if "user" not in session:
        session["user"] = {"email": "auto@ecole.com", "id": "auto"}

def get_all_candidats():
    response = supabase.table("candidats").select("*").order("created_at", desc=True).execute()
    return response.data

def get_candidat_by_id(candidat_id):
    response = supabase.table("candidats").select("*").eq("id", candidat_id).execute()
    return response.data[0] if response.data else None

@app.route("/")
def index():
    candidats = get_all_candidats()
    return render_template("index.html", candidats=candidats)

@app.route("/add", methods=["GET", "POST"])
def add_candidat():
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
                    flash("Photo trop grande (max 5 Mo)")
                    return redirect(url_for("add_candidat"))
                supabase_admin.storage.from_("photos_candidats").upload(
                    filename, file_bytes, {"content-type": file.mimetype or "image/jpeg"}
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
        supabase.table("candidats").insert(data).execute()
        flash("Candidat ajouté")
        return redirect(url_for("index"))
    return render_template("add_candidat.html")

@app.route("/candidat/<candidat_id>")
def candidat_detail(candidat_id):
    candidat = get_candidat_by_id(candidat_id)
    if not candidat:
        flash("Candidat introuvable")
        return redirect(url_for("index"))
    return render_template("candidat_detail.html", c=candidat)

@app.route("/edit/<candidat_id>", methods=["GET", "POST"])
def edit_candidat(candidat_id):
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
                    flash("Photo trop grande (max 5 Mo)")
                    return redirect(url_for("edit_candidat", candidat_id=candidat_id))
                supabase_admin.storage.from_("photos_candidats").upload(
                    filename, file_bytes, {"content-type": file.mimetype or "image/jpeg"}
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
        supabase.table("candidats").update(data).eq("id", candidat_id).execute()
        flash("Modifié")
        return redirect(url_for("candidat_detail", candidat_id=candidat_id))
    
    return render_template("add_candidat.html", candidat=candidat)

@app.route("/delete/<candidat_id>")
def delete_candidat(candidat_id):
    supabase.table("candidats").delete().eq("id", candidat_id).execute()
    flash("Supprimé")
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)