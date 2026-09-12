"""Model providers — one OpenAI-compatible interface for all of them.

Every provider speaks the OpenAI chat-completions API: DeepSeek natively,
Anthropic and Google Gemini through their official OpenAI compatibility
layers, and Ollama through its built-in ``/v1`` server. ORION therefore needs
a single client class and no extra SDKs.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_env: str
    default_model: str
    input_price: float
    output_price: float
    local: bool = False


PROVIDERS: dict[str, Provider] = {
    "deepseek": Provider(
        name="deepseek",
        base_url="https://api.deepseek.com",
        key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        input_price=0.27,
        output_price=1.10,
    ),
    "anthropic": Provider(
        name="anthropic",
        base_url="https://api.anthropic.com/v1/",
        key_env="ANTHROPIC_API_KEY",
        default_model="claude-sonnet-4-5",
        input_price=3.00,
        output_price=15.00,
    ),
    "openai": Provider(
        name="openai",
        base_url="https://api.openai.com/v1",
        key_env="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        input_price=0.15,
        output_price=0.60,
    ),
    "gemini": Provider(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_env="GEMINI_API_KEY",
        default_model="gemini-2.0-flash",
        input_price=0.10,
        output_price=0.40,
    ),
    "ollama": Provider(
        name="ollama",
        base_url="http://localhost:11434/v1",
        key_env="OLLAMA_API_KEY",
        default_model="llama3.2",
        input_price=0.0,
        output_price=0.0,
        local=True,
    ),
}


def get_provider(name: str) -> Provider:
    """Return the provider registry entry; unknown names raise ``ValueError``."""
    try:
        return PROVIDERS[name.lower().strip()]
    except KeyError:
        raise ValueError(f"Unknown provider: {name}. Available: {', '.join(PROVIDERS)}") from None


def resolve_api_key(provider: Provider) -> str:
    """Read the provider API key; local providers get a stub key."""
    key = os.getenv(provider.key_env, "").strip()
    if key:
        return key
    return "ollama" if provider.local else ""


def default_provider() -> Provider:
    """The provider configured via ``ORION_PROVIDER`` (default: deepseek)."""
    name = os.getenv("ORION_PROVIDER", "deepseek").strip().lower() or "deepseek"
    return get_provider(name)
