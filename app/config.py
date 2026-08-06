"""
Module: app/config.py

Purpose:
    Single source of truth for all runtime configuration. Loads `.env` once
    and exposes a typed `Settings` singleton. No other module in this
    codebase is permitted to read `os.environ` directly (see Master Spec
    §9.2 and §13) — everything goes through `get_settings()`.

Inputs:
    - `.env` file at the project root (git-ignored). See Master Spec §12.1
      for the canonical list of keys.

Outputs:
    - `Settings` dataclass instance (singleton, via `get_settings()`).

Depends on:
    - python-dotenv

Called by:
    - app/main.py (startup env validation, app factory)
    - app/routes.py (upload limits, settings endpoints)
    - Indirectly referenced by other packages (rag/, tools/, models/) which
      should import `get_settings()` from here rather than reading env vars
      themselves.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Project root = two levels up from this file (app/config.py -> app/ -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Load .env once, at import time. Safe to call multiple times; python-dotenv
# no-ops if the file is missing.
load_dotenv(dotenv_path=ENV_PATH)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _get_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {key!r} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    """Typed, immutable snapshot of runtime configuration."""

    # --- Model / API ---
    gemini_api_key: str = field(default_factory=lambda: _get_str("GEMINI_API_KEY"))

    # --- Storage paths ---
    chroma_persist_dir: str = field(default_factory=lambda: _get_str("CHROMA_PERSIST_DIR", "./database/chroma_db"))
    json_store_dir: str = field(default_factory=lambda: _get_str("JSON_STORE_DIR", "./database"))

    # --- Reliability ---
    max_retries: int = field(default_factory=lambda: _get_int("MAX_RETRIES", 3))

    # --- Logging ---
    log_level: str = field(default_factory=lambda: _get_str("LOG_LEVEL", "INFO"))

    # --- Notifications ---
    notification_email_from: str = field(default_factory=lambda: _get_str("NOTIFICATION_EMAIL_FROM"))
    notification_smtp_host: str = field(default_factory=lambda: _get_str("NOTIFICATION_SMTP_HOST"))
    notification_smtp_port: int = field(default_factory=lambda: _get_int("NOTIFICATION_SMTP_PORT", 587))

    # --- Derived, fixed application constants (not env-configurable) ---
    upload_max_bytes: int = 25 * 1024 * 1024  # 25 MB, per Master Spec §9.3
    allowed_upload_extensions: tuple = (".pdf", ".txt", ".csv")

    # --- Resolved absolute paths (computed, not read from env directly) ---
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def chroma_persist_path(self) -> Path:
        return (PROJECT_ROOT / self.chroma_persist_dir).resolve()

    @property
    def json_store_path(self) -> Path:
        return (PROJECT_ROOT / self.json_store_dir).resolve()

    @property
    def user_data_path(self) -> Path:
        return self.json_store_path / "user_data.json"

    @property
    def conversation_memory_path(self) -> Path:
        return self.json_store_path / "conversation_memory.json"

    @property
    def task_history_path(self) -> Path:
        return self.json_store_path / "task_history.json"

    @property
    def system_log_path(self) -> Path:
        return PROJECT_ROOT / "logs" / "system_logs.txt"

    def validate_required(self) -> None:
        """Fail-fast check used by app/main.py at startup. Raises ConfigError
        if a required setting is missing. Called once, before the app
        starts serving requests."""
        missing = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + f". Set them in {ENV_PATH}."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the process-wide Settings singleton. Cached so `.env` is
    parsed once per process."""
    return Settings()