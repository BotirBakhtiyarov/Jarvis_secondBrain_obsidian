import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project .env wins over the global one (load_dotenv never overrides).
load_dotenv()
load_dotenv(Path.home() / ".orion" / ".env")

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_LANGUAGE = "en"

# USD per 1M tokens (approximate; override via .env)
DEFAULT_INPUT_PRICE = 0.27
DEFAULT_OUTPUT_PRICE = 1.10


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
    tavily_api_key: str = ""


def load_config(overrides: dict | None = None) -> Config:
    """Load configuration from .env; CLI overrides win."""

    overrides = overrides or {}

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

    vault_raw = overrides.get("vault") or os.getenv("OBSIDIAN_VAULT", "")
    if not vault_raw:
        raise ValueError(
            "OBSIDIAN_VAULT not found in .env. Example: OBSIDIAN_VAULT=/home/user/SecondBrain"
        )

    workspace_raw = overrides.get("workspace") or os.getenv("WORKSPACE") or str(Path.cwd())

    history_raw = os.getenv("ORION_HISTORY") or str(Path.home() / ".orion" / "history.json")

    return Config(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
        model=overrides.get("model") or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
        obsidian_vault=Path(vault_raw).expanduser().resolve(),
        workspace=Path(workspace_raw).expanduser().resolve(),
        history_path=Path(history_raw).expanduser().resolve(),
        max_history=int(os.getenv("ORION_MAX_HISTORY", "50")),
        language=(os.getenv("ORION_LANG", DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE),
        input_price=float(os.getenv("DEEPSEEK_INPUT_PRICE", DEFAULT_INPUT_PRICE)),
        output_price=float(os.getenv("DEEPSEEK_OUTPUT_PRICE", DEFAULT_OUTPUT_PRICE)),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
    )
