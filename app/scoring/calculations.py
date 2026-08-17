"""Berekeningen: schaal-normalisatie, gewogen puntentotalen, knock-out-uitsluiting.

Een "score"-criterium met weging W (procentpunten van de 100 totaal) en schaal
[min, max] levert bij score S een gewogen bijdrage van:

    punten = (S - min) / (max - min) * W

Zo tellen alle criteria samen, bij de maximale score overal, op tot exact de
som van hun wegingen (die op hun beurt optellen tot 100%).
"""
from __future__ import annotations

import re

_SCHAAL_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*-\s*(-?\d+(?:[.,]\d+)?)\s*$")


def parse_schaal(schaal: str | None) -> tuple[float, float]:
    if not schaal:
        return (0.0, 10.0)
    m = _SCHAAL_RE.match(schaal)
    if not m:
        return (0.0, 10.0)
    lo = float(m.group(1).replace(",", "."))
    hi = float(m.group(2).replace(",", "."))
    if hi <= lo:
        return (0.0, 10.0)
    return (lo, hi)


def criterium_punten(criterium: dict, score: float | None) -> float:
    if criterium.get("type") == "knock-out" or score is None:
        return 0.0
    lo, hi = parse_schaal(criterium.get("schaal"))
    genormaliseerd = max(0.0, min(1.0, (float(score) - lo) / (hi - lo)))
    return genormaliseerd * float(criterium.get("weging") or 0)


def compute_supplier_totals(matrix: list[dict], scores: dict[str, dict]) -> dict:
    """`scores` = {criterium_id: score-record dict (uit db.list_scores)}.

    Retourneert per categorie een subtotaal, een eindtotaal, en of de
    leverancier is uitgesloten op basis van een niet-gehaald knock-outcriterium.
    """
    categorie_resultaten = []
    eindtotaal = 0.0
    uitgesloten = False
    gefaalde_criteria = []

    for cat in matrix:
        cat_punten = 0.0
        for crit in cat.get("criteria", []):
            rec = scores.get(crit["id"])
            if crit.get("type") == "knock-out":
                voldaan = rec.get("voldaan") if rec else None
                if voldaan == 0:
                    uitgesloten = True
                    gefaalde_criteria.append(crit["naam"])
                continue
            score_waarde = rec.get("score") if rec else None
            cat_punten += criterium_punten(crit, score_waarde)
        categorie_resultaten.append({
            "categorie_id": cat["id"],
            "categorie_naam": cat["naam"],
            "weging": cat.get("weging", 0),
            "punten": round(cat_punten, 2),
        })
        eindtotaal += cat_punten

    return {
        "categorieen": categorie_resultaten,
        "eindtotaal": round(eindtotaal, 2),
        "uitgesloten": uitgesloten,
        "gefaalde_knockout_criteria": gefaalde_criteria,
    }


def all_criteria_flat(matrix: list[dict]) -> list[dict]:
    """Platte lijst van alle criteria (met categorie-info erbij), matrix-volgorde."""
    out = []
    for cat in matrix:
        for crit in cat.get("criteria", []):
            out.append({**crit, "categorie_naam": cat["naam"], "categorie_id": cat["id"]})
    return out
