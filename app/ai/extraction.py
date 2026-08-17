"""Gedeelde bouwsteen voor 'grondige' tweetraps-AI-analyse.

In plaats van alle brondocumenten in één grote aanroep te proppen (waarbij een model —
zeker een kleiner/gratis model — makkelijk iets vergeet ergens middenin een lange
context), wordt eerst per document, en bij lange documenten per sectie ("chunk"),
een volledige lijst van relevante items geëxtraheerd. Pas daarna worden die combineert
tot het eindresultaat (matrix of scores) — zie matrix_generation.py / scoring.py.

Dit kost meer AI-aanroepen (grofweg: aantal documenten/chunks + 1 synthese-aanroep,
i.p.v. 1 aanroep), maar verbetert de grondigheid aanzienlijk, vooral bij minder sterke
modellen. Bij gratis/rate-gelimiteerde modellen kan dit sneller tegen een limiet aanlopen
— dat is een bewuste afweging (grondigheid boven aanroepefficiëntie).
"""
from __future__ import annotations

from app.ai.client import chat_json

CHUNK_GROOTTE = 60_000  # tekens; documenten groter dan dit worden in stukken gesplitst
CHUNK_OVERLAP = 2_000   # overlap om eisen die precies op een chunkgrens vallen niet te missen


def _chunk_tekst(tekst: str) -> list[str]:
    if len(tekst) <= CHUNK_GROOTTE:
        return [tekst]
    chunks = []
    start = 0
    while start < len(tekst):
        eind = min(start + CHUNK_GROOTTE, len(tekst))
        chunks.append(tekst[start:eind])
        if eind >= len(tekst):
            break
        start = eind - CHUNK_OVERLAP
    return chunks


def extract_items(documents: list[dict], system_prompt: str, max_tokens: int = 8000) -> list[dict]:
    """Voert de extractie-aanroep uit per document/chunk en voegt de resultaten samen.

    `documents` = [{"bestandsnaam": str, "type": str, "tekst": str}, ...]
    `system_prompt` bepaalt wat er precies geëxtraheerd wordt; het model moet antwoorden
    met JSON in de vorm {"items": [{..., "sectie": "..."}]}. Elk item krijgt hier een
    samengesteld 'bron'-veld (bestandsnaam + sectie) en het aparte 'sectie'-veld vervalt.
    """
    alle_items: list[dict] = []
    for doc in documents:
        chunks = _chunk_tekst(doc["tekst"])
        for i, chunk in enumerate(chunks, start=1):
            chunk_label = f" (deel {i}/{len(chunks)})" if len(chunks) > 1 else ""
            user_prompt = (
                f"Document: {doc['bestandsnaam']} (type: {doc.get('type', '')}){chunk_label}\n\n{chunk}"
            )
            result = chat_json(system_prompt, user_prompt, max_tokens=max_tokens)
            for item in result.get("items", []):
                if not isinstance(item, dict):
                    continue
                sectie = item.get("sectie") or ""
                bron = doc["bestandsnaam"] + (f", {sectie}" if sectie else "")
                item = dict(item)
                item.pop("sectie", None)
                item["bron"] = bron
                alle_items.append(item)
    return alle_items
