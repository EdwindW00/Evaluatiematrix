"""End-to-end testscenario voor fase 4-8, met synthetische scores (geen AI-key nodig).

Maakt een testproject met een matrix (incl. knock-out) en twee leveranciers, waarvan er
één het knock-outcriterium niet haalt. Print de resulterende URL's om handmatig te
verifiëren, en print de berekende totalen ter controle.
"""
from app.db import projects as db
from app.db.schema import init_db
from app.scoring.calculations import compute_supplier_totals

init_db()

pid = db.create_project("E2E-test Fase 4-8", "Testopdrachtgever")

db.replace_matrix(pid, [
    {
        "naam": "Kwaliteit",
        "weging": 60,
        "criteria": [
            {"naam": "Plan van aanpak", "type": "score", "schaal": "0-10", "weging": 25,
             "bron": "RFQ.docx", "toelichting": "Kwaliteit van het plan van aanpak."},
            {"naam": "Ervaring", "type": "score", "schaal": "0-10", "weging": 20,
             "bron": "RFQ.docx", "toelichting": "Aantal en relevantie referenties."},
            {"naam": "Duurzaamheid", "type": "score", "schaal": "0-10", "weging": 15,
             "bron": "RFQ.docx", "toelichting": "Duurzaamheidsbeleid."},
        ],
    },
    {
        "naam": "Prijs",
        "weging": 40,
        "criteria": [
            {"naam": "Jaarprijs", "type": "score", "schaal": "0-10", "weging": 40,
             "bron": "Prijsbijlage.xlsx", "toelichting": "Lagere prijs = hogere score."},
        ],
    },
    {
        "naam": "Knock-out",
        "weging": 0,
        "criteria": [
            {"naam": "ISO 9001-certificaat", "type": "knock-out", "bron": "RFQ.docx",
             "toelichting": "Verplicht geldig certificaat."},
        ],
    },
])

matrix = db.get_matrix(pid)
crit_by_naam = {c["naam"]: c["id"] for cat in matrix for c in cat["criteria"]}

sid_a = db.add_supplier(pid, "Schoonmaakbedrijf Alpha")
sid_b = db.add_supplier(pid, "Schoonmaakbedrijf Beta (uitgesloten)")

# Leverancier A: goede scores, voldoet aan knock-out
db.upsert_score(sid_a, crit_by_naam["Plan van aanpak"], score=8, onderbouwing="Uitgebreid en concreet plan.",
                 citaat="Wij hanteren een KPI-dashboard per locatie.", vertrouwen="duidelijk vermeld")
db.upsert_score(sid_a, crit_by_naam["Ervaring"], score=7, onderbouwing="4 relevante referenties genoemd.",
                 citaat="Sinds 2021 verzorgen wij soortgelijke dienstverlening.", vertrouwen="duidelijk vermeld")
db.upsert_score(sid_a, crit_by_naam["Duurzaamheid"], score=6, onderbouwing="Duurzaamheidsbeleid summier beschreven.",
                 citaat="Wij gebruiken milieuvriendelijke middelen.", vertrouwen="afgeleid, niet expliciet")
db.upsert_score(sid_a, crit_by_naam["Jaarprijs"], score=9, onderbouwing="Scherpe prijs t.o.v. de markt.",
                 citaat="", vertrouwen="duidelijk vermeld")
db.upsert_score(sid_a, crit_by_naam["ISO 9001-certificaat"], voldaan=1, onderbouwing="Certificaat als bijlage toegevoegd.",
                 citaat="Zie bijlage 4: ISO 9001:2015-certificaat.", vertrouwen="duidelijk vermeld")
db.set_supplier_status(sid_a, "gescoord")

# Leverancier B: haalt de knock-out niet (geen certificaat)
db.upsert_score(sid_b, crit_by_naam["Plan van aanpak"], score=9, onderbouwing="Zeer sterk plan.",
                 citaat="", vertrouwen="duidelijk vermeld")
db.upsert_score(sid_b, crit_by_naam["Ervaring"], score=8, onderbouwing="Ruime ervaring.", citaat="",
                 vertrouwen="duidelijk vermeld")
db.upsert_score(sid_b, crit_by_naam["Duurzaamheid"], score=9, onderbouwing="Zeer uitgebreid duurzaamheidsbeleid.",
                 citaat="", vertrouwen="duidelijk vermeld")
db.upsert_score(sid_b, crit_by_naam["Jaarprijs"], score=8, onderbouwing="Concurrerende prijs.", citaat="",
                 vertrouwen="duidelijk vermeld")
db.upsert_score(sid_b, crit_by_naam["ISO 9001-certificaat"], voldaan=0,
                 onderbouwing="Geen ISO 9001-certificaat aangetroffen in de offerte.", citaat="",
                 vertrouwen="niet gevonden in de offerte")
db.set_supplier_status(sid_b, "gescoord")
db.set_supplier_excluded(sid_b, True)

for sid, naam in [(sid_a, "Alpha"), (sid_b, "Beta")]:
    scores = db.list_scores(sid)
    totalen = compute_supplier_totals(matrix, scores)
    print(f"{naam}: eindtotaal={totalen['eindtotaal']} uitgesloten={totalen['uitgesloten']} "
          f"categorieen={totalen['categorieen']}")

print(f"\nPROJECT_ID={pid}")
print(f"Project:   http://127.0.0.1:5151/project/{pid}")
print(f"Leverancier A: http://127.0.0.1:5151/project/{pid}/leverancier/{sid_a}")
print(f"Leverancier B: http://127.0.0.1:5151/project/{pid}/leverancier/{sid_b}")
print(f"Dashboard: http://127.0.0.1:5151/project/{pid}/dashboard")
print(f"Export:    http://127.0.0.1:5151/project/{pid}/export/volledig")
