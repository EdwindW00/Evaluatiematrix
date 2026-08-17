"""Flask-webinterface voor de Evaluatiematrix-app."""
from __future__ import annotations

import os
import secrets
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from app.ai import matrix_generation, scoring as ai_scoring
from app.ai.client import AIError, is_configured
from app.config import (
    AI_PROVIDERS,
    ALLOWED_UPLOAD_EXTENSIONS,
    DEFAULT_AI_PROVIDER,
    ENV_FILE,
    project_dir,
    project_input_dir,
    project_supplier_dir,
    get_ai_api_key,
    get_ai_model,
    get_ai_provider,
)
from app.db import projects as db
from app.db.schema import init_db
from app.export.excel_export import export_full, export_matrix
from app.ingest.extract import ExtractionError, extract_text, suggest_document_type
from app.scoring.calculations import all_criteria_flat, compute_supplier_totals

FASEN = [
    ("upload", "1. Brondocumenten"),
    ("matrix", "2. Matrix genereren & reviewen"),
    ("offertes", "3. Offertes"),
    ("dashboard", "4. Dashboard"),
]


def _basic_auth_vereist() -> tuple[str, str] | None:
    """Geeft (gebruikersnaam, wachtwoord) terug als APP_USERNAME/APP_PASSWORD zijn ingesteld
    (bijv. bij een publieke deploy), anders None — lokaal gebruik blijft dan zonder inlog."""
    gebruiker = os.environ.get("APP_USERNAME")
    wachtwoord = os.environ.get("APP_PASSWORD")
    if gebruiker and wachtwoord:
        return gebruiker, wachtwoord
    return None


def create_app() -> Flask:
    app = Flask(__name__)
    init_db()

    # ---------------------------------------------------------------- toegangsbeveiliging
    # Alleen actief als APP_USERNAME/APP_PASSWORD zijn ingesteld (bedoeld voor een publieke
    # deploy, bijv. op Render) — bij lokaal gebruik op je eigen computer blijft de app zoals
    # altijd zonder inlogscherm.

    @app.before_request
    def _vereis_basic_auth():
        vereist = _basic_auth_vereist()
        if not vereist:
            return None
        verwacht_gebruiker, verwacht_wachtwoord = vereist
        auth = request.authorization
        if (
            auth
            and secrets.compare_digest(auth.username or "", verwacht_gebruiker)
            and secrets.compare_digest(auth.password or "", verwacht_wachtwoord)
        ):
            return None
        return Response(
            "Inloggen vereist.", 401,
            {"WWW-Authenticate": 'Basic realm="Evaluatiematrix-assistent"'},
        )

    # ---------------------------------------------------------------- projecten

    @app.route("/")
    def index():
        return render_template("index.html", projecten=db.list_projects())

    @app.route("/projects", methods=["POST"])
    def create_project():
        naam = request.form.get("naam", "").strip()
        opdrachtgever = request.form.get("opdrachtgever", "").strip()
        if not naam:
            return redirect(url_for("index"))
        pid = db.create_project(naam, opdrachtgever)
        return redirect(url_for("project_detail", project_id=pid))

    @app.route("/project/<project_id>/rename", methods=["POST"])
    def rename_project(project_id):
        naam = request.form.get("naam", "").strip()
        if naam:
            db.rename_project(project_id, naam)
        return redirect(url_for("project_detail", project_id=project_id))

    @app.route("/project/<project_id>/archive", methods=["POST"])
    def archive_project(project_id):
        db.set_project_status(project_id, "gearchiveerd")
        return redirect(url_for("index"))

    @app.route("/project/<project_id>/delete", methods=["POST"])
    def delete_project(project_id):
        db.delete_project(project_id)
        return redirect(url_for("index"))

    @app.route("/project/<project_id>")
    def project_detail(project_id):
        project = db.get_project(project_id)
        if not project:
            return redirect(url_for("index"))
        leveranciers = db.list_suppliers(project_id)
        for lev in leveranciers:
            lev["documenten"] = db.list_supplier_documents(lev["id"])
        return render_template(
            "project.html",
            project=project,
            fasen=FASEN,
            documenten=db.list_documents(project_id),
            matrix=db.get_matrix(project_id),
            leveranciers=leveranciers,
            ai_geconfigureerd=is_configured(),
        )

    # ---------------------------------------------------------------- documenten

    @app.route("/project/<project_id>/upload", methods=["POST"])
    def upload_documents(project_id):
        project = db.get_project(project_id)
        if not project:
            return jsonify({"error": "project niet gevonden"}), 404

        target_dir = project_input_dir(project_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        resultaten = []
        for f in request.files.getlist("bestanden"):
            if not f.filename:
                continue
            ext = Path(f.filename).suffix.lower()
            if ext not in ALLOWED_UPLOAD_EXTENSIONS:
                resultaten.append({"bestandsnaam": f.filename, "status": "fout",
                                    "foutmelding": f"Bestandstype '{ext}' wordt niet ondersteund."})
                continue

            veilige_naam = secure_filename(f.filename) or f"document-{uuid.uuid4().hex[:8]}{ext}"
            doel_pad = target_dir / veilige_naam
            teller = 1
            while doel_pad.exists():
                doel_pad = target_dir / f"{Path(veilige_naam).stem}_{teller}{ext}"
                teller += 1
            f.save(doel_pad)

            doc_id = db.add_document(project_id, f.filename, str(doel_pad))
            db.set_document_status(doc_id, "bezig")
            try:
                tekst = extract_text(doel_pad)
                type_suggestie = suggest_document_type(f.filename, tekst)
                db.update_document_type(doc_id, type_suggestie)
                db.set_document_status(doc_id, "klaar", geextraheerde_tekst=tekst)
                resultaten.append({"id": doc_id, "bestandsnaam": f.filename, "status": "klaar",
                                    "type": type_suggestie})
            except ExtractionError as e:
                db.set_document_status(doc_id, "fout", foutmelding=str(e))
                resultaten.append({"id": doc_id, "bestandsnaam": f.filename, "status": "fout",
                                    "foutmelding": str(e)})

        return jsonify({"resultaten": resultaten, "documenten": db.list_documents(project_id)})

    @app.route("/project/<project_id>/documents/<doc_id>/type", methods=["POST"])
    def update_document_type(project_id, doc_id):
        type_ = request.form.get("type", "overig")
        db.update_document_type(doc_id, type_)
        return jsonify({"ok": True})

    @app.route("/project/<project_id>/documents/<doc_id>/delete", methods=["POST"])
    def delete_document(project_id, doc_id):
        doc = db.get_document(doc_id)
        if doc:
            try:
                Path(doc["pad"]).unlink(missing_ok=True)
            except OSError:
                pass
            db.delete_document(doc_id)
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- matrix

    @app.route("/project/<project_id>/matrix/genereren", methods=["POST"])
    def generate_matrix(project_id):
        docs = [d for d in db.list_documents(project_id) if d["status"] == "klaar"]
        if not docs:
            return jsonify({"error": "Geen succesvol verwerkte brondocumenten gevonden."}), 400
        payload = [{"bestandsnaam": d["bestandsnaam"], "type": d["type"], "tekst": d["geextraheerde_tekst"] or ""}
                   for d in docs]
        try:
            resultaat = matrix_generation.generate_matrix(payload)
        except AIError as e:
            return jsonify({"error": str(e)}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        db.replace_matrix(project_id, resultaat.get("categorieen", []))
        return jsonify({
            "matrix": db.get_matrix(project_id),
            "onzekerheden": resultaat.get("onzekerheden", []),
        })

    @app.route("/project/<project_id>/matrix", methods=["GET"])
    def get_matrix(project_id):
        return jsonify({"matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/categorie", methods=["POST"])
    def add_category(project_id):
        naam = request.json.get("naam", "Nieuwe categorie")
        cat_id = db.add_category(project_id, naam)
        return jsonify({"id": cat_id, "matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/categorie/<cat_id>", methods=["PATCH"])
    def update_category(project_id, cat_id):
        data = request.json or {}
        db.update_category(cat_id, naam=data.get("naam"), weging=data.get("weging"))
        return jsonify({"matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/categorie/<cat_id>", methods=["DELETE"])
    def delete_category(project_id, cat_id):
        db.delete_category(cat_id)
        return jsonify({"matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/categorie/<cat_id>/criterium", methods=["POST"])
    def add_criterion(project_id, cat_id):
        data = request.json or {}
        crit_id = db.add_criterion(
            project_id, cat_id, naam=data.get("naam", "Nieuw criterium"),
            type_=data.get("type", "score"), schaal=data.get("schaal", "0-10"),
            weging=data.get("weging", 0), bron=data.get("bron", ""),
            toelichting=data.get("toelichting", ""),
        )
        return jsonify({"id": crit_id, "matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/criterium/<crit_id>", methods=["PATCH"])
    def update_criterion(project_id, crit_id):
        data = request.json or {}
        db.update_criterion(crit_id, **data)
        return jsonify({"matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/criterium/<crit_id>", methods=["DELETE"])
    def delete_criterion(project_id, crit_id):
        db.delete_criterion(crit_id)
        return jsonify({"matrix": db.get_matrix(project_id)})

    @app.route("/project/<project_id>/matrix/vaststellen", methods=["POST"])
    def lock_matrix(project_id):
        db.set_matrix_status(project_id, "vastgesteld")
        return jsonify({"ok": True})

    @app.route("/project/<project_id>/matrix/heropenen", methods=["POST"])
    def unlock_matrix(project_id):
        db.set_matrix_status(project_id, "concept")
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- leveranciers (fase 4)

    @app.route("/project/<project_id>/leveranciers", methods=["POST"])
    def add_supplier(project_id):
        naam = request.form.get("naam", "").strip()
        if not naam:
            return jsonify({"error": "Naam is verplicht."}), 400
        sid = db.add_supplier(project_id, naam)
        return jsonify({"id": sid, "naam": naam, "status": "nog niet gescoord",
                         "uitgesloten": 0, "documenten": []})

    @app.route("/project/<project_id>/leveranciers/<supplier_id>/delete", methods=["POST"])
    def delete_supplier(project_id, supplier_id):
        db.delete_supplier(supplier_id, project_id)
        return jsonify({"ok": True})

    @app.route("/project/<project_id>/leveranciers/<supplier_id>/upload", methods=["POST"])
    def upload_supplier_documents(project_id, supplier_id):
        target_dir = project_supplier_dir(project_id, supplier_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        resultaten = []
        for f in request.files.getlist("bestanden"):
            if not f.filename:
                continue
            ext = Path(f.filename).suffix.lower()
            if ext not in ALLOWED_UPLOAD_EXTENSIONS:
                resultaten.append({"bestandsnaam": f.filename, "status": "fout",
                                    "foutmelding": f"Bestandstype '{ext}' wordt niet ondersteund."})
                continue
            veilige_naam = secure_filename(f.filename) or f"document-{uuid.uuid4().hex[:8]}{ext}"
            doel_pad = target_dir / veilige_naam
            teller = 1
            while doel_pad.exists():
                doel_pad = target_dir / f"{Path(veilige_naam).stem}_{teller}{ext}"
                teller += 1
            f.save(doel_pad)

            doc_id = db.add_supplier_document(supplier_id, f.filename, str(doel_pad))
            db.set_supplier_document_status(doc_id, "bezig")
            try:
                tekst = extract_text(doel_pad)
                db.set_supplier_document_status(doc_id, "klaar", geextraheerde_tekst=tekst)
            except ExtractionError as e:
                db.set_supplier_document_status(doc_id, "fout", foutmelding=str(e))

        return jsonify({"documenten": db.list_supplier_documents(supplier_id)})

    @app.route("/project/<project_id>/leveranciers/<supplier_id>/documenten/<doc_id>/delete", methods=["POST"])
    def delete_supplier_document(project_id, supplier_id, doc_id):
        from app.db.schema import get_conn
        with get_conn() as conn:
            row = conn.execute("SELECT pad FROM leverancier_documenten WHERE id = ?", (doc_id,)).fetchone()
            if row:
                try:
                    Path(row["pad"]).unlink(missing_ok=True)
                except OSError:
                    pass
            conn.execute("DELETE FROM leverancier_documenten WHERE id = ?", (doc_id,))
        return jsonify({"documenten": db.list_supplier_documents(supplier_id)})

    # ---------------------------------------------------------------- scoring (fase 5 & 6)

    @app.route("/project/<project_id>/leveranciers/<supplier_id>/scoren", methods=["POST"])
    def score_supplier(project_id, supplier_id):
        supplier = db.get_supplier(supplier_id)
        matrix = db.get_matrix(project_id)
        criteria = all_criteria_flat(matrix)
        if not criteria:
            return jsonify({"error": "De matrix bevat nog geen criteria."}), 400

        docs = [d for d in db.list_supplier_documents(supplier_id) if d["status"] == "klaar"]
        if not docs:
            return jsonify({"error": "Geen succesvol verwerkte offertedocumenten gevonden."}), 400

        payload = [{"bestandsnaam": d["bestandsnaam"], "tekst": d["geextraheerde_tekst"] or "",
                    "leverancier_naam": supplier["naam"]} for d in docs]

        db.set_supplier_status(supplier_id, "bezig")
        try:
            resultaten = ai_scoring.generate_scores(criteria, payload)
        except AIError as e:
            db.set_supplier_status(supplier_id, "nog niet gescoord")
            return jsonify({"error": str(e)}), 400
        except ValueError as e:
            db.set_supplier_status(supplier_id, "nog niet gescoord")
            return jsonify({"error": str(e)}), 400

        for r in resultaten:
            db.upsert_score(
                supplier_id, r["criterium_id"], score=r["score"], voldaan=r["voldaan"],
                onderbouwing=r["onderbouwing"], citaat=r["citaat"], vertrouwen=r["vertrouwen"],
                overschreven_door_gebruiker=0,
            )
        db.set_supplier_status(supplier_id, "gescoord")

        knock_out_gefaald = any(
            r["voldaan"] == 0 for r in resultaten
        )
        db.set_supplier_excluded(supplier_id, knock_out_gefaald)

        return jsonify({"ok": True, "scores": db.list_scores(supplier_id),
                         "status": "gescoord", "uitgesloten": knock_out_gefaald})

    @app.route("/project/<project_id>/leverancier/<supplier_id>")
    def supplier_detail(project_id, supplier_id):
        project = db.get_project(project_id)
        supplier = db.get_supplier(supplier_id)
        if not project or not supplier:
            return redirect(url_for("project_detail", project_id=project_id))
        matrix = db.get_matrix(project_id)
        scores = db.list_scores(supplier_id)
        totalen = compute_supplier_totals(matrix, scores)
        return render_template(
            "leverancier.html", project=project, supplier=supplier, matrix=matrix,
            scores=scores, totalen=totalen,
        )

    @app.route("/project/<project_id>/leverancier/<supplier_id>/score/<crit_id>", methods=["PATCH"])
    def update_score(project_id, supplier_id, crit_id):
        data = request.json or {}
        velden = {}
        if "score" in data:
            velden["score"] = data["score"]
        if "voldaan" in data:
            velden["voldaan"] = data["voldaan"]
        if "gebruiker_commentaar" in data:
            velden["gebruiker_commentaar"] = data["gebruiker_commentaar"]
        if "nader_verifieren" in data:
            velden["nader_verifieren"] = 1 if data["nader_verifieren"] else 0
        velden["overschreven_door_gebruiker"] = 1
        db.upsert_score(supplier_id, crit_id, **velden)

        matrix = db.get_matrix(project_id)
        scores = db.list_scores(supplier_id)
        totalen = compute_supplier_totals(matrix, scores)
        knock_out_gefaald = totalen["uitgesloten"]
        db.set_supplier_excluded(supplier_id, knock_out_gefaald)
        db.set_supplier_status(supplier_id, "handmatig gecontroleerd")
        return jsonify({"totalen": totalen})

    @app.route("/project/<project_id>/leverancier/<supplier_id>/gecontroleerd", methods=["POST"])
    def mark_supplier_reviewed(project_id, supplier_id):
        db.set_supplier_status(supplier_id, "handmatig gecontroleerd")
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- dashboard (fase 7)

    @app.route("/project/<project_id>/dashboard")
    def dashboard(project_id):
        project = db.get_project(project_id)
        matrix = db.get_matrix(project_id)
        leveranciers = db.list_suppliers(project_id)
        overzicht = []
        for lev in leveranciers:
            scores = db.list_scores(lev["id"])
            totalen = compute_supplier_totals(matrix, scores)
            overzicht.append({"leverancier": lev, "totalen": totalen, "scores": scores})
        # Ranking: uitgesloten leveranciers onderaan, verder op eindtotaal
        overzicht.sort(key=lambda o: (o["totalen"]["uitgesloten"], -o["totalen"]["eindtotaal"]))
        return render_template("dashboard.html", project=project, matrix=matrix, overzicht=overzicht)

    # ---------------------------------------------------------------- export

    @app.route("/project/<project_id>/export/matrix")
    def export_matrix_route(project_id):
        project = db.get_project(project_id)
        matrix = db.get_matrix(project_id)
        output_path = project_dir(project_id) / "output" / "evaluatiematrix.xlsx"
        export_matrix(project, matrix, output_path)
        return send_file(output_path, as_attachment=True,
                          download_name=f"Evaluatiematrix_{project['naam']}.xlsx")

    @app.route("/project/<project_id>/export/volledig")
    def export_full_route(project_id):
        project = db.get_project(project_id)
        matrix = db.get_matrix(project_id)
        leveranciers = db.list_suppliers(project_id)
        scores_per_leverancier = {lev["id"]: db.list_scores(lev["id"]) for lev in leveranciers}
        totalen_per_leverancier = {
            lev_id: compute_supplier_totals(matrix, scores)
            for lev_id, scores in scores_per_leverancier.items()
        }
        output_path = project_dir(project_id) / "output" / "evaluatiematrix_volledig.xlsx"
        export_full(project, matrix, leveranciers, scores_per_leverancier, totalen_per_leverancier, output_path)
        return send_file(output_path, as_attachment=True,
                          download_name=f"Evaluatiematrix_{project['naam']}_volledig.xlsx")

    # ---------------------------------------------------------------- instellingen

    @app.route("/instellingen", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            provider = request.form.get("provider", "").strip()
            if provider not in AI_PROVIDERS:
                provider = DEFAULT_AI_PROVIDER
            api_key = request.form.get("api_key", "").strip()
            model = request.form.get("model", "").strip() or AI_PROVIDERS[provider]["default_model"]

            lines = [f"AI_PROVIDER={provider}"]
            if api_key:
                lines.append(f"AI_API_KEY={api_key}")
            else:
                # geen nieuwe key ingevuld: behoud de bestaande (indien aanwezig en zelfde provider)
                bestaande_provider = get_ai_provider()
                bestaande_key = get_ai_api_key()
                if bestaande_key and bestaande_provider == provider:
                    lines.append(f"AI_API_KEY={bestaande_key}")
            lines.append(f"AI_MODEL={model}")
            ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return redirect(url_for("settings"))
        return render_template(
            "settings.html", geconfigureerd=is_configured(),
            api_key_masked=_mask(get_ai_api_key()),
            huidig_model=get_ai_model(), huidige_provider=get_ai_provider(),
            providers=AI_PROVIDERS,
        )

    @app.route("/instellingen/api-key/verwijderen", methods=["POST"])
    def delete_api_key():
        provider = get_ai_provider()
        model = get_ai_model()
        ENV_FILE.write_text(f"AI_PROVIDER={provider}\nAI_MODEL={model}\n", encoding="utf-8")
        return redirect(url_for("settings"))

    return app


def _mask(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return key[:4] + "…" + key[-4:]
