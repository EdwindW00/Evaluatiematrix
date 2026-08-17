"""AI-analyse van brondocumenten → conceptmatrix (categorieën, criteria, wegingen).

Tweetraps-aanpak voor grondigheid:
  1. **Extractie** (app.ai.extraction): per document/sectie wordt uitputtend elke eis,
     clausule, norm, KPI, termijn of boete genoteerd — een gerichte, smalle taak waarbij
     een model minder snel iets overslaat dan wanneer het meteen alles moet lezen én
     structureren.
  2. **Synthese**: de volledige, samengevoegde eisenlijst (al voorzien van brongegevens)
     wordt omgezet naar de uiteindelijke matrix met categorieën, wegingen en knock-outs.

Dit kost meer AI-aanroepen dan één enkele aanroep, maar is aantoonbaar grondiger —
zie de vergelijkingstest met een synthetisch SLA-document (2026-08-14).
"""
from __future__ import annotations

from app.ai import extraction
from app.ai.client import chat_json

EISEN_EXTRACTIE_PROMPT = """\
Je bent een zeer nauwkeurige Nederlandse contract- en aanbestedingsanalist. Je taak is NIET \
om een evaluatiematrix te maken — je taak is om UITPUTTEND elke eis, clausule, norm, KPI, \
termijn, boete, certificeringseis of ander concreet gunnings- of contractrelevant gegeven te \
noteren dat in het aangeleverde tekstfragment voorkomt. Mis niets, ook geen kleine details \
(getallen, percentages, termijnen, certificeringen, escalatieprocedures). Antwoord ALTIJD in \
geldig JSON, in het Nederlands, met exact deze structuur:

{
  "items": [
    {
      "omschrijving": "korte, specifieke omschrijving van de eis/clausule",
      "categorie_gok": "vrije inschatting: Kwaliteit / Prijs / Duurzaamheid / Implementatie / Organisatie / Contractueel / Overig",
      "type_gok": "knock-out of score — knock-out als het een harde ja/nee-eis is, anders score",
      "citaat": "kort letterlijk citaat uit de tekst (max ~2 zinnen)",
      "sectie": "sectie/artikelnummer of paragraaftitel indien herkenbaar, anders leeg"
    }
  ]
}

Wees liever te uitgebreid dan te beknopt — elke gemiste eis is een risico bij een latere \
aanbestedingsprocedure (bezwaar/kort geding). Neem ALLE eisen op, ook als ze op het eerste \
gezicht niet gunningsrelevant lijken (bijv. contractuele boetes, rapportage-eisen); een latere \
synthesestap filtert en structureert dit tot de uiteindelijke matrix.
"""

SYNTHESE_SYSTEM_PROMPT = """\
Je bent een ervaren Nederlandse inkoop- en aanbestedingsexpert die evaluatiematrixen \
(EMVI/BPKV) opstelt voor tenders in facility management en dienstverlening.

Je krijgt een reeds volledig geëxtraheerde lijst van eisen/clausules uit alle brondocumenten \
van een tender (elk met een geschatte categorie, geschat type, een citaat en een bronverwijzing). \
Groepeer, dedupliceer en structureer deze tot een conceptmatrix met gunningscriteria. Antwoord \
ALTIJD in geldig JSON, in het Nederlands, met exact deze structuur:

{
  "categorieen": [
    {
      "naam": "string, bijv. Kwaliteit",
      "weging": 40,
      "criteria": [
        {
          "naam": "string",
          "type": "score" of "knock-out",
          "schaal": "0-10",
          "weging": 15,
          "bron": "bestandsnaam, sectie/fragment waar dit criterium vandaan komt (uit de brongegevens van de eis)",
          "toelichting": "hoe te beoordelen; wat een hoge versus lage score onderscheidt — verwerk relevante concrete details (getallen, termijnen, normen) uit de eisenlijst hierin"
        }
      ]
    }
  ],
  "onzekerheden": [
    "beschrijving van tegenstrijdige, dubbele, of onduidelijke eisen tussen documenten, indien van toepassing"
  ]
}

Regels:
- Gebruik ALLE relevante eisen uit de aangeleverde lijst — dit is de volledige extractie van de \
  brondocumenten, dus behandel elke eis serieus. Combineer eisen die feitelijk hetzelfde criterium \
  beschrijven (ook als ze uit verschillende documenten komen) tot één criterium, en vermeld dan \
  beide bronnen.
- Wegingen van categorieën tellen op tot 100. Wegingen van criteria binnen een categorie tellen \
  op tot de weging van die categorie.
- Knock-outcriteria (type "knock-out") krijgen GEEN "schaal" en GEEN "weging" (zet weging op 0).
- Gebruik correcte Nederlandse aanbestedingsterminologie.
- Signaleer expliciet in "onzekerheden" wanneer eisen uit verschillende documenten elkaar \
  tegenspreken (bijv. een eis die in de offerte-aanvraag niet als knock-out staat maar in de SLA \
  wel een harde eis blijkt, of omgekeerd).
"""


def build_synthese_prompt(eisen: list[dict]) -> str:
    regels = []
    for i, e in enumerate(eisen, start=1):
        regels.append(
            f"{i}. [{e.get('bron', '')}] (gok: {e.get('categorie_gok', '')} / {e.get('type_gok', '')}) "
            f"{e.get('omschrijving', '')} — citaat: \"{e.get('citaat', '')}\""
        )
    eisen_tekst = "\n".join(regels)
    return (
        "Onderstaande lijst is de volledige, reeds geëxtraheerde verzameling eisen/clausules uit "
        "alle brondocumenten van deze tender. Structureer dit tot een conceptmatrix conform de "
        "opgegeven JSON-structuur.\n\n" + eisen_tekst
    )


def generate_matrix(documents: list[dict]) -> dict:
    """Genereert een conceptmatrix via de tweetraps-aanpak (extractie + synthese).

    Gooit AIError bij problemen (zie app.ai.client); ValueError als er geen documenten zijn.
    """
    if not documents:
        raise ValueError("Geen documenten om te analyseren.")

    eisen = extraction.extract_items(documents, EISEN_EXTRACTIE_PROMPT, max_tokens=8000)
    if not eisen:
        raise ValueError(
            "Geen eisen/clausules gevonden in de brondocumenten — controleer of de "
            "tekstextractie geslaagd is (zie documentstatus bij Brondocumenten)."
        )

    user_prompt = build_synthese_prompt(eisen)
    result = chat_json(SYNTHESE_SYSTEM_PROMPT, user_prompt, max_tokens=12000)
    result.setdefault("categorieen", [])
    result.setdefault("onzekerheden", [])
    return result
