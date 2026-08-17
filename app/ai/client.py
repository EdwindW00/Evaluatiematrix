"""Minimale AI-chatclient via de standaardbibliotheek `urllib`.

Bewust geen SDK-package als dependency (consistent met de aanpak in de bestaande
IFM Tender-Prep Assistent). Ondersteunt meerdere OpenAI-compatibele providers
(OpenAI zelf, OpenRouter, NVIDIA NIM) achter dezelfde chat-completions-vorm, elk
met hun eigen endpoint en key-formaat. De API-key wordt alleen lokaal gelezen uit
.env / omgevingsvariabele — nooit hardcoded, nooit verstuurd behalve naar het
gekozen provider-endpoint zelf.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from app.config import get_ai_api_key, get_ai_model, get_ai_provider, get_provider_info

_JSON_BLOK_RE = re.compile(r"\{.*\}", re.DOTALL)

# (Vooral gratis/gedeelde modellen kunnen incidenteel een misvormd/leeg antwoord geven
# onder belasting — bijv. exact dezelfde aanroep lukt de ene keer wel en de andere keer
# niet.) Bij zulke transiente fouten wordt automatisch opnieuw geprobeerd.
MAX_POGINGEN = 3
TERUGVAL_SECONDEN = [4, 12]  # wachttijd vóór poging 2 en poging 3


class AIError(Exception):
    """Nette, Nederlandstalige foutmelding voor AI-aanroepen."""


class _TransientAIError(Exception):
    """Interne markering voor fouten waarbij een nieuwe poging zinvol is."""


def is_configured() -> bool:
    return bool(get_ai_api_key())


def chat_json(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> dict:
    """Roept het geconfigureerde AI-model aan en parseert de respons als JSON.

    Gebruikt `response_format: json_object` op providers die dat ondersteunen (OpenAI);
    bij andere providers (OpenRouter, NVIDIA NIM) leunt dit op de instructie in de
    system-prompt en wordt een eventueel omringend stuk tekst/markdown-codeblok
    rond de JSON er automatisch afgehaald.

    Transiente fouten (verbindingsproblemen, tijdelijke overbelasting, een misvormd
    antwoord) worden automatisch een paar keer opnieuw geprobeerd voordat een AIError
    naar boven komt.
    """
    laatste_fout: Exception | None = None
    for poging in range(1, MAX_POGINGEN + 1):
        try:
            return _chat_json_attempt(system_prompt, user_prompt, max_tokens)
        except _TransientAIError as e:
            laatste_fout = e
            if poging < MAX_POGINGEN:
                time.sleep(TERUGVAL_SECONDEN[poging - 1])
                continue
            raise AIError(f"{e} (na {MAX_POGINGEN} pogingen)") from e
    # onbereikbaar, maar voor de type-checker:
    raise AIError(str(laatste_fout))


def _chat_json_attempt(system_prompt: str, user_prompt: str, max_tokens: int) -> dict:
    api_key = get_ai_api_key()
    provider = get_ai_provider()
    info = get_provider_info(provider)
    if not api_key:
        raise AIError(
            f"Geen API-key ingesteld voor {info['label']}. Vul deze in via het "
            "instellingenscherm voordat je AI-functies gebruikt."
        )

    payload = {
        "model": get_ai_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if info["supports_json_mode"]:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        info["base_url"],
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=280) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise AIError(
                f"De {info['label']}-key wordt geweigerd (HTTP {e.code} — ongeldig, verlopen, of "
                f"een key van een andere provider). {info['label']}-keys beginnen met "
                f"'{info['key_prefix_hint']}'. Detail: {detail[:200]}"
            ) from e
        if e.code == 429:
            raise _TransientAIError(f"{info['label']}-limiet bereikt (HTTP 429)") from e
        if e.code >= 500:
            raise _TransientAIError(f"{info['label']}-serverfout (HTTP {e.code})") from e
        raise AIError(f"{info['label']}-API-fout (HTTP {e.code}): {detail[:300]}") from e
    except urllib.error.URLError as e:
        raise _TransientAIError(f"Kon geen verbinding maken met {info['label']}: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise _TransientAIError(f"Onleesbaar (niet-JSON) antwoord van {info['label']}: {e}") from e

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        # Sommige (vooral gratis/gedeelde) modellen geven onder belasting incidenteel een
        # misvormd antwoord terug — vaak met een 'error'-veld i.p.v. 'choices'. Dat is de
        # moeite van een nieuwe poging waard.
        fout_detail = body.get("error") if isinstance(body, dict) else None
        raise _TransientAIError(
            f"Onverwacht antwoordformaat van {info['label']} ({e})"
            + (f" — foutmelding in respons: {fout_detail}" if fout_detail else "")
        ) from e

    if not content or not content.strip():
        raise _TransientAIError(f"{info['label']} gaf een leeg antwoord terug")

    return _parse_json_content(content, info["label"])


def _parse_json_content(content: str, provider_label: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Sommige modellen (vooral zonder afgedwongen JSON-modus) wikkelen het antwoord
    # in een ```json ... ```-codeblok of voegen er wat inleidende tekst aan toe.
    match = _JSON_BLOK_RE.search(content)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise AIError(
        f"Kon het antwoord van {provider_label} niet als JSON lezen. "
        f"Begin van het antwoord: {content[:200]!r}"
    )
