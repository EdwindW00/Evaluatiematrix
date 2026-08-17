"""Paden en instellingen voor de Evaluatiematrix-app.

Alles draait lokaal. Er is geen externe database; per project worden
brondocumenten op schijf bewaard en alle gestructureerde data (matrix,
scores, versiegeschiedenis) in één lokale SQLite-database.
"""
from __future__ import annotations

import os
from pathlib import Path

# Projectroot = map waarin dit package staat (…/evaluatiematrix-app)
APP_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = APP_ROOT / "projects"
DB_PATH = PROJECTS_ROOT / "evaluatiematrix.db"

# Huisstijl (zie app-spec: donkerblauw primair, accentblauw interactief)
KLEUR_PRIMAIR = "1A4E8C"
KLEUR_ACCENT = "2E6DB4"

# .env-bestand met de AI-providerinstellingen (nooit hardcoden, nooit meesturen in code)
ENV_FILE = APP_ROOT / ".env"

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt"}
MAX_UPLOAD_SIZE_MB = 50

# Ondersteunde AI-providers — allemaal een OpenAI-compatibele chat-completions-API,
# maar met een eigen endpoint en (soms) beperktere ondersteuning voor JSON-afdwinging.
# Let op de key-prefixen: OpenAI-keys beginnen met "sk-", OpenRouter-keys met "sk-or-v1-",
# NVIDIA NIM-keys met "nvapi-" — een key van de verkeerde provider wordt altijd geweigerd.
AI_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o",
        "key_prefix_hint": "sk-...",
        "supports_json_mode": True,
        "voorbeeldmodellen": ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        # Gratis-tier default (geen tegoed nodig) — het grootste/capabelste model in
        # OpenRouter's ":free"-aanbod (1M-tokens context). Zodra er tegoed op het account
        # staat is "anthropic/claude-opus-5" de aanbevolen upgrade voor kwaliteit boven prijs.
        "default_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "key_prefix_hint": "sk-or-v1-...",
        "supports_json_mode": False,
        # OpenRouter-modelnamen zijn altijd "leverancier/modelnaam" — nooit alleen de leveranciersnaam.
        "voorbeeldmodellen": [
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "anthropic/claude-opus-5",
            "anthropic/claude-sonnet-5",
            "openai/gpt-4o-mini",
        ],
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "default_model": "meta/llama-3.1-70b-instruct",
        "key_prefix_hint": "nvapi-...",
        "supports_json_mode": False,
        "voorbeeldmodellen": ["meta/llama-3.1-70b-instruct", "mistralai/mixtral-8x7b-instruct-v0.1"],
    },
}
DEFAULT_AI_PROVIDER = "openai"


def project_dir(project_id: str) -> Path:
    return PROJECTS_ROOT / project_id


def project_input_dir(project_id: str) -> Path:
    return project_dir(project_id) / "input"


def project_supplier_dir(project_id: str, supplier_id: str) -> Path:
    return project_dir(project_id) / "leveranciers" / supplier_id


def ensure_dirs() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


def _read_env_file() -> dict[str, str]:
    """Leest .env vers van schijf bij elke aanroep (geen caching in os.environ) —
    zodat verwijderen/wijzigen van een waarde meteen effect heeft, zonder herstart."""
    waarden: dict[str, str] = {}
    if not ENV_FILE.exists():
        return waarden
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            waarden[key] = value
    return waarden


def get_ai_provider() -> str:
    """Actieve AI-provider ('openai' | 'openrouter' | 'nvidia'). Onbekende/lege waarde -> default."""
    waarde = _read_env_file().get("AI_PROVIDER") or os.environ.get("AI_PROVIDER") or DEFAULT_AI_PROVIDER
    return waarde if waarde in AI_PROVIDERS else DEFAULT_AI_PROVIDER


def get_ai_api_key() -> str | None:
    env = _read_env_file()
    # AI_API_KEY is de huidige naam; OPENAI_API_KEY blijft werken voor bestaande .env-bestanden
    return env.get("AI_API_KEY") or env.get("OPENAI_API_KEY") or os.environ.get("AI_API_KEY") or None


def get_ai_model() -> str:
    env = _read_env_file()
    opgeslagen = env.get("AI_MODEL") or env.get("OPENAI_MODEL") or os.environ.get("AI_MODEL")
    if opgeslagen:
        return opgeslagen
    return AI_PROVIDERS[get_ai_provider()]["default_model"]


def get_provider_info(provider: str | None = None) -> dict:
    return AI_PROVIDERS[provider or get_ai_provider()]


# Backward-compatible aliassen (worden elders nog gebruikt/kunnen extern verwacht worden)
def get_openai_api_key() -> str | None:
    return get_ai_api_key()


def get_openai_model() -> str:
    return get_ai_model()
