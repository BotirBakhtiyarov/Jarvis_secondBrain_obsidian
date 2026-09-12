import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from orion import providers

# Project .env wins over the global one (load_dotenv never overrides).
load_dotenv()
load_dotenv(Path.home() / ".orion" / ".env")

DEFAULT_LANGUAGE = "en"


@dataclass
class Config:
    api_key: str
    base_url: str
    model: str
    obsidian_vault: Path
    workspace: Path
    history_path: Path
    max_history: int
    input_price: float
    output_price: float
    language: str = "en"
    provider: str = "deepseek"
    tavily_api_key: str = ""
    client: object = None
    registry: object = None


def _first_env(*names: str) -> str:
    for name in names:
        raw = os.getenv(name, "").strip()
        if raw:
            return raw
    return ""


def _price(name: str, legacy: str, fallback: float, provider_name: str) -> float:
    """Price override: ORION_* for any provider, legacy DEEPSEEK_* kept working."""
    raw = os.getenv(name, "").strip()
    if not raw and provider_name == "deepseek":
        raw = os.getenv(legacy, "").strip()
    return float(raw) if raw else fallback


def load_config(overrides: dict | None = None) -> Config:
    """Load configuration from .env; CLI overrides win."""

    overrides = overrides or {}

    provider = providers.get_provider(os.getenv("ORION_PROVIDER", "deepseek"))
    api_key = providers.resolve_api_key(provider)

    vault_raw = overrides.get("vault") or os.getenv("OBSIDIAN_VAULT", "")
    if not vault_raw:
        raise ValueError(
            "OBSIDIAN_VAULT not found in .env. Example: OBSIDIAN_VAULT=/home/user/SecondBrain"
        )

    workspace_raw = overrides.get("workspace") or os.getenv("WORKSPACE") or str(Path.cwd())
    history_raw = os.getenv("ORION_HISTORY") or str(Path.home() / ".orion" / "history.json")

    # ORION_* overrides any provider; legacy DEEPSEEK_* still work on deepseek.
    base_url = (
        _first_env("ORION_BASE_URL")
        or (_first_env("DEEPSEEK_BASE_URL") if provider.name == "deepseek" else "")
        or provider.base_url
    )
    model = (
        overrides.get("model")
        or _first_env("ORION_MODEL")
        or (_first_env("DEEPSEEK_MODEL") if provider.name == "deepseek" else "")
        or provider.default_model
    )

    return Config(
        api_key=api_key,
        base_url=base_url,
        model=model,
        obsidian_vault=Path(vault_raw).expanduser().resolve(),
        workspace=Path(workspace_raw).expanduser().resolve(),
        history_path=Path(history_raw).expanduser().resolve(),
        max_history=int(os.getenv("ORION_MAX_HISTORY", "50")),
        language=(os.getenv("ORION_LANG", DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE),
        input_price=_price(
            "ORION_INPUT_PRICE", "DEEPSEEK_INPUT_PRICE", provider.input_price, provider.name
        ),
        output_price=_price(
            "ORION_OUTPUT_PRICE", "DEEPSEEK_OUTPUT_PRICE", provider.output_price, provider.name
        ),
        provider=provider.name,
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
    )
