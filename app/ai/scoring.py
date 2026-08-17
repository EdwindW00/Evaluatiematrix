"""AI-scoring van een leverancier-offerte tegen de vastgestelde matrix.

Zelfde tweetraps-aanpak als matrixgeneratie (zie app.ai.matrix_generation):
  1. **Extractie**: per offertedocument/sectie wordt uitputtend elke concrete bewering,
     toezegging, kwalificatie of onderbouwing genoteerd — los van de criteria, puur "wat
     staat hier letterlijk".
  2. **Synthese**: de volledige, samengevoegde beweringenlijst (met citaten en bron) wordt
     tegen elk criterium gelegd om tot een score/onderbouwing/citaat te komen.

Dit voorkomt dat details die diep in een lange offerte begraven zitten over het hoofd
worden gezien wanneer een model de hele offerte in één keer moet doorgronden.
"""
from __future__ import annotations

from app.ai import extraction
from app.ai.client import chat_json

BEWERING_EXTRACTIE_PROMPT = """\
Je bent een zeer nauwkeurige Nederlandse tenderanalist. Je taak is NIET om een offerte te \
scoren — je taak is om UITPUTTEND elke concrete bewering, toezegging, kwalificatie, referentie, \
cijfer, certificering of onderbouwing te noteren die in het aangeleverde offertefragment \
voorkomt. Mis niets, ook geen kleine details. Antwoord ALTIJD in geldig JSON, in het Nederlands, \
met exact deze structuur:

{
  "items": [
    {
      "omschrijving": "korte, specifieke omschrijving van de bewering/toezegging",
      "citaat": "kort letterlijk citaat uit de offerte (max ~2 zinnen)",
      "sectie": "sectie/paragraaftitel indien herkenbaar, anders leeg"
    }
  ]
}

Wees liever te uitgebreid dan te beknopt — elke gemiste bewering kan een leverancier \
onterecht een lagere score opleveren. Neem ALLE concrete beweringen op, ook als het nut \
ervan nu nog niet duidelijk is; een latere stap matcht dit tegen de gunningscriteria.
"""

SYNTHESE_SYSTEM_PROMPT = """\
Je bent een ervaren Nederlandse inkoop- en aanbestedingsexpert die offertes beoordeelt \
tegen vastgestelde gunningscriteria (EMVI/BPKV) voor tenders in facility management en \
dienstverlening.

Je krijgt een lijst gunningscriteria (elk met een volgnummer) en een reeds volledig \
geëxtraheerde lijst van beweringen/toezeggingen uit de offerte van één leverancier (elk met \
een citaat en een bronverwijzing). Beoordeel de offerte per criterium op basis van deze \
beweringenlijst en antwoord ALTIJD in geldig JSON, in het Nederlands, met exact deze structuur:

{
  "scores": [
    {
      "criterium_index": 1,
      "type": "score",
      "score": 7,
      "voldaan": null,
      "onderbouwing": "korte onderbouwing in het Nederlands",
      "citaat": "kort letterlijk citaat uit de beweringenlijst dat de score onderbouwt",
      "vertrouwen": "duidelijk vermeld" | "afgeleid, niet expliciet" | "niet gevonden in de offerte"
    },
    {
      "criterium_index": 2,
      "type": "knock-out",
      "score": null,
      "voldaan": true,
      "onderbouwing": "korte onderbouwing",
      "citaat": "kort citaat",
      "vertrouwen": "duidelijk vermeld"
    }
  ]
}

Regels:
- Doorzoek de VOLLEDIGE beweringenlijst voor elk criterium — deze lijst is de complete \
  extractie van de offerte, dus een relevante bewering kan overal in de lijst staan.
- Voor "score"-criteria: geef een score binnen de opgegeven schaal, en zet "voldaan" op null.
- Voor "knock-out"-criteria: geef "voldaan" (true/false), en zet "score" op null. Alleen \
  false wanneer de offerte expliciet niet aan de eis voldoet of de eis niet aantoont; als je \
  het echt niet kunt beoordelen, zet dan "voldaan": false EN "vertrouwen": "niet gevonden in \
  de offerte" (transparantie boven twijfel).
- Geef voor ELK criterium uit de lijst precies één resultaat, in dezelfde volgorde/index.
- Als geen enkele bewering een criterium raakt: score/voldaan zo neutraal/laag mogelijk \
  inschatten, "vertrouwen": "niet gevonden in de offerte", en dit ook in de onderbouwing melden.
- Citeer alleen tekst die daadwerkelijk in de beweringenlijst voorkomt (traceerbaarheid is \
  belangrijk bij een eventueel bezwaar van een afgewezen inschrijver).
"""


def build_synthese_prompt(criteria: list[dict], bewijzen: list[dict], leverancier_naam: str) -> str:
    crit_lines = []
    for i, c in enumerate(criteria, start=1):
        if c.get("type") == "knock-out":
            crit_lines.append(f"{i}. [KNOCK-OUT] {c['naam']} — {c.get('toelichting', '')}")
        else:
            crit_lines.append(
                f"{i}. [SCORE, schaal {c.get('schaal', '0-10')}] {c['naam']} — {c.get('toelichting', '')}"
            )
    criteria_tekst = "\n".join(crit_lines)

    bewijs_lines = [
        f"- [{b.get('bron', '')}] {b.get('omschrijving', '')} — citaat: \"{b.get('citaat', '')}\""
        for b in bewijzen
    ]
    bewijs_tekst = "\n".join(bewijs_lines) if bewijs_lines else "(geen beweringen geëxtraheerd)"

    return (
        f"Gunningscriteria:\n{criteria_tekst}\n\n"
        f"Volledig geëxtraheerde beweringenlijst uit de offerte van leverancier "
        f"'{leverancier_naam}':\n\n{bewijs_tekst}"
    )


def generate_scores(criteria: list[dict], documents: list[dict]) -> list[dict]:
    """`criteria` = platte lijst (app.scoring.calculations.all_criteria_flat).
    `documents` = [{"bestandsnaam", "tekst", "leverancier_naam"}, ...]
    Retourneert een lijst even lang als `criteria`, in dezelfde volgorde.
    """
    if not criteria:
        return []
    if not documents:
        raise ValueError("Geen offertedocumenten om te analyseren.")

    leverancier_naam = documents[0]["leverancier_naam"]
    bewijzen = extraction.extract_items(documents, BEWERING_EXTRACTIE_PROMPT, max_tokens=8000)

    user_prompt = build_synthese_prompt(criteria, bewijzen, leverancier_naam)
    result = chat_json(SYNTHESE_SYSTEM_PROMPT, user_prompt, max_tokens=12000)
    ruwe_scores = result.get("scores", [])
    by_index = {r.get("criterium_index"): r for r in ruwe_scores if isinstance(r, dict)}

    out = []
    for i, crit in enumerate(criteria, start=1):
        r = by_index.get(i, {})
        out.append({
            "criterium_id": crit["id"],
            "score": r.get("score"),
            "voldaan": (1 if r.get("voldaan") is True else (0 if r.get("voldaan") is False else None)),
            "onderbouwing": r.get("onderbouwing", ""),
            "citaat": r.get("citaat", ""),
            "vertrouwen": r.get("vertrouwen", "niet gevonden in de offerte"),
        })
    return out
