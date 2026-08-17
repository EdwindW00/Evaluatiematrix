"""CRUD-functies voor projecten, documenten, matrix, leveranciers en scores."""
from __future__ import annotations

import shutil

from app.config import project_dir, project_input_dir, project_supplier_dir
from app.db.schema import get_conn, new_id, now_iso


# ---------------------------------------------------------------- projecten

def create_project(naam: str, opdrachtgever: str = "") -> str:
    pid = new_id()
    ts = now_iso()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO projects (id, naam, opdrachtgever, aangemaakt_op, bijgewerkt_op) "
            "VALUES (?, ?, ?, ?, ?)",
            (pid, naam, opdrachtgever, ts, ts),
        )
    project_input_dir(pid).mkdir(parents=True, exist_ok=True)
    return pid


def list_projects(include_archived: bool = False):
    with get_conn() as conn:
        if include_archived:
            rows = conn.execute("SELECT * FROM projects ORDER BY bijgewerkt_op DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status != 'gearchiveerd' ORDER BY bijgewerkt_op DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


def rename_project(project_id: str, naam: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET naam = ?, bijgewerkt_op = ? WHERE id = ?",
            (naam, now_iso(), project_id),
        )


def set_project_status(project_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET status = ?, bijgewerkt_op = ? WHERE id = ?",
            (status, now_iso(), project_id),
        )


def touch_project(project_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE projects SET bijgewerkt_op = ? WHERE id = ?", (now_iso(), project_id))


def delete_project(project_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    d = project_dir(project_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def set_matrix_status(project_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET matrix_status = ?, bijgewerkt_op = ? WHERE id = ?",
            (status, now_iso(), project_id),
        )


# ---------------------------------------------------------------- documenten

def add_document(project_id: str, bestandsnaam: str, pad: str, type_: str = "overig") -> str:
    did = new_id()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO documenten (id, project_id, bestandsnaam, pad, type, status, geupload_op) "
            "VALUES (?, ?, ?, ?, ?, 'wachten', ?)",
            (did, project_id, bestandsnaam, pad, type_, now_iso()),
        )
    touch_project(project_id)
    return did


def list_documents(project_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documenten WHERE project_id = ? ORDER BY geupload_op", (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_document_type(doc_id: str, type_: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE documenten SET type = ? WHERE id = ?", (type_, doc_id))


def set_document_status(doc_id: str, status: str, foutmelding: str | None = None,
                         geextraheerde_tekst: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE documenten SET status = ?, foutmelding = ?, "
            "geextraheerde_tekst = COALESCE(?, geextraheerde_tekst) WHERE id = ?",
            (status, foutmelding, geextraheerde_tekst, doc_id),
        )


def get_document(doc_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documenten WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def delete_document(doc_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM documenten WHERE id = ?", (doc_id,))


# ---------------------------------------------------------------- matrix

def replace_matrix(project_id: str, categorieen: list[dict]) -> None:
    """Vervangt de volledige matrix (categorieën + criteria) van een project.

    `categorieen` = [{naam, weging, criteria: [{naam, type, schaal, weging, bron, toelichting}, ...]}, ...]
    Bestaande scores blijven behouden zolang criterium-id's niet veranderen; bij een
    volledige vervanging (nieuwe generatie) worden oude criteria + hun scores verwijderd.
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM criteria WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM categorieen WHERE project_id = ?", (project_id,))
        for ci, cat in enumerate(categorieen):
            cat_id = cat.get("id") or new_id()
            conn.execute(
                "INSERT INTO categorieen (id, project_id, naam, weging, volgorde) VALUES (?, ?, ?, ?, ?)",
                (cat_id, project_id, cat["naam"], cat.get("weging", 0), ci),
            )
            for ki, crit in enumerate(cat.get("criteria", [])):
                crit_id = crit.get("id") or new_id()
                conn.execute(
                    "INSERT INTO criteria (id, project_id, categorie_id, naam, type, schaal, weging, "
                    "bron, toelichting, volgorde) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        crit_id, project_id, cat_id, crit["naam"], crit.get("type", "score"),
                        crit.get("schaal", "0-10"), crit.get("weging", 0), crit.get("bron", ""),
                        crit.get("toelichting", ""), ki,
                    ),
                )
    set_matrix_status(project_id, "concept")
    touch_project(project_id)


def get_matrix(project_id: str) -> list[dict]:
    with get_conn() as conn:
        cats = conn.execute(
            "SELECT * FROM categorieen WHERE project_id = ? ORDER BY volgorde", (project_id,)
        ).fetchall()
        out = []
        for cat in cats:
            crits = conn.execute(
                "SELECT * FROM criteria WHERE categorie_id = ? ORDER BY volgorde", (cat["id"],)
            ).fetchall()
            d = dict(cat)
            d["criteria"] = [dict(c) for c in crits]
            out.append(d)
        return out


def update_category(cat_id: str, naam: str | None = None, weging: float | None = None) -> None:
    with get_conn() as conn:
        if naam is not None:
            conn.execute("UPDATE categorieen SET naam = ? WHERE id = ?", (naam, cat_id))
        if weging is not None:
            conn.execute("UPDATE categorieen SET weging = ? WHERE id = ?", (weging, cat_id))


def update_criterion(crit_id: str, **velden) -> None:
    if not velden:
        return
    allowed = {"naam", "type", "schaal", "weging", "bron", "toelichting", "categorie_id", "volgorde"}
    sets, params = [], []
    for k, v in velden.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return
    params.append(crit_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE criteria SET {', '.join(sets)} WHERE id = ?", params)


def add_category(project_id: str, naam: str, weging: float = 0) -> str:
    cat_id = new_id()
    with get_conn() as conn:
        volgorde = conn.execute(
            "SELECT COALESCE(MAX(volgorde), -1) + 1 FROM categorieen WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO categorieen (id, project_id, naam, weging, volgorde) VALUES (?, ?, ?, ?, ?)",
            (cat_id, project_id, naam, weging, volgorde),
        )
    return cat_id


def delete_category(cat_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM categorieen WHERE id = ?", (cat_id,))


def add_criterion(project_id: str, categorie_id: str, naam: str, type_: str = "score",
                   schaal: str = "0-10", weging: float = 0, bron: str = "", toelichting: str = "") -> str:
    crit_id = new_id()
    with get_conn() as conn:
        volgorde = conn.execute(
            "SELECT COALESCE(MAX(volgorde), -1) + 1 FROM criteria WHERE categorie_id = ?", (categorie_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO criteria (id, project_id, categorie_id, naam, type, schaal, weging, bron, "
            "toelichting, volgorde) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (crit_id, project_id, categorie_id, naam, type_, schaal, weging, bron, toelichting, volgorde),
        )
    return crit_id


def delete_criterion(crit_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM criteria WHERE id = ?", (crit_id,))


# ---------------------------------------------------------------- leveranciers

def add_supplier(project_id: str, naam: str) -> str:
    sid = new_id()
    with get_conn() as conn:
        volgorde = conn.execute(
            "SELECT COALESCE(MAX(volgorde), -1) + 1 FROM leveranciers WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO leveranciers (id, project_id, naam, volgorde) VALUES (?, ?, ?, ?)",
            (sid, project_id, naam, volgorde),
        )
    project_supplier_dir(project_id, sid).mkdir(parents=True, exist_ok=True)
    touch_project(project_id)
    return sid


def list_suppliers(project_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM leveranciers WHERE project_id = ? ORDER BY volgorde", (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_supplier(supplier_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM leveranciers WHERE id = ?", (supplier_id,)).fetchone()
        return dict(row) if row else None


def set_supplier_status(supplier_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE leveranciers SET status = ? WHERE id = ?", (status, supplier_id))


def set_supplier_excluded(supplier_id: str, uitgesloten: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE leveranciers SET uitgesloten = ? WHERE id = ?", (1 if uitgesloten else 0, supplier_id)
        )


def delete_supplier(supplier_id: str, project_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM leveranciers WHERE id = ?", (supplier_id,))
    d = project_supplier_dir(project_id, supplier_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def add_supplier_document(supplier_id: str, bestandsnaam: str, pad: str) -> str:
    did = new_id()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO leverancier_documenten (id, leverancier_id, bestandsnaam, pad, status, geupload_op) "
            "VALUES (?, ?, ?, ?, 'wachten', ?)",
            (did, supplier_id, bestandsnaam, pad, now_iso()),
        )
    return did


def list_supplier_documents(supplier_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM leverancier_documenten WHERE leverancier_id = ? ORDER BY geupload_op",
            (supplier_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_supplier_document_status(doc_id: str, status: str, foutmelding: str | None = None,
                                  geextraheerde_tekst: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE leverancier_documenten SET status = ?, foutmelding = ?, "
            "geextraheerde_tekst = COALESCE(?, geextraheerde_tekst) WHERE id = ?",
            (status, foutmelding, geextraheerde_tekst, doc_id),
        )


# ---------------------------------------------------------------- scores

def upsert_score(leverancier_id: str, criterium_id: str, **velden) -> None:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM scores WHERE leverancier_id = ? AND criterium_id = ?",
            (leverancier_id, criterium_id),
        ).fetchone()
        cols = ["score", "voldaan", "onderbouwing", "citaat", "vertrouwen",
                "overschreven_door_gebruiker", "gebruiker_commentaar", "nader_verifieren"]
        if existing:
            sets, params = [], []
            for c in cols:
                if c in velden:
                    sets.append(f"{c} = ?")
                    params.append(velden[c])
            sets.append("bijgewerkt_op = ?")
            params.append(now_iso())
            params.append(existing["id"])
            if sets:
                conn.execute(f"UPDATE scores SET {', '.join(sets)} WHERE id = ?", params)
        else:
            sid = new_id()
            conn.execute(
                "INSERT INTO scores (id, leverancier_id, criterium_id, score, voldaan, onderbouwing, "
                "citaat, vertrouwen, overschreven_door_gebruiker, gebruiker_commentaar, nader_verifieren, "
                "bijgewerkt_op) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sid, leverancier_id, criterium_id, velden.get("score"), velden.get("voldaan"),
                    velden.get("onderbouwing"), velden.get("citaat"), velden.get("vertrouwen"),
                    velden.get("overschreven_door_gebruiker", 0), velden.get("gebruiker_commentaar"),
                    velden.get("nader_verifieren", 0), now_iso(),
                ),
            )


def list_scores(leverancier_id: str):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM scores WHERE leverancier_id = ?", (leverancier_id,)).fetchall()
        return {r["criterium_id"]: dict(r) for r in rows}
