from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OWNER = "00000000-0000-0000-0000-000000000002"


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    # REST API
    gateway_url: str = "http://localhost:8080"
    default_owner_id: str | None = DEFAULT_OWNER
    allowed_owner_ids: tuple[str, ...] = (DEFAULT_OWNER,)
    http_timeout: float = 5.0

    # LLM
    llm_model: str = "gpt-4.1-mini"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_reasoning: str = "auto"  # auto | true | false
    llm_token_param: str = "max_completion_tokens"

    # Guardrails: витрати
    max_tokens_per_call: int = 800
    token_budget: int = 20_000
    max_steps: int = 10
    max_tool_calls: int = 12
    max_tool_result_chars: int = 3000
    max_list_items: int = 20
    max_prompt_chars: int = 4000

    # Guardrails: безпека
    confirm_writes: bool = True

    # MCP
    mcp_read_only: bool = False
    mcp_calls_per_minute: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        default_owner = os.getenv("DEFAULT_OWNER_ID", DEFAULT_OWNER).strip().lower() or None
        allowed_raw = os.getenv("ALLOWED_OWNER_IDS", "")
        allowed = tuple(x.strip().lower() for x in allowed_raw.split(",") if x.strip())
        if not allowed and default_owner:
            allowed = (default_owner,)
        return cls(
            gateway_url=os.getenv("GATEWAY_URL", "http://localhost:8080").rstrip("/"),
            default_owner_id=default_owner,
            allowed_owner_ids=allowed,
            http_timeout=_float("HTTP_TIMEOUT", 5.0),
            llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            llm_base_url=os.getenv("LLM_BASE_URL") or None,
            llm_api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or None,
            llm_reasoning=os.getenv("LLM_REASONING", "auto").lower(),
            llm_token_param=os.getenv("LLM_TOKEN_PARAM", "max_completion_tokens"),
            max_tokens_per_call=_int("MAX_TOKENS_PER_CALL", 800),
            token_budget=_int("TOKEN_BUDGET", 20_000),
            max_steps=_int("MAX_STEPS", 10),
            max_tool_calls=_int("MAX_TOOL_CALLS", 12),
            max_tool_result_chars=_int("MAX_TOOL_RESULT_CHARS", 3000),
            max_list_items=_int("MAX_LIST_ITEMS", 20),
            max_prompt_chars=_int("MAX_PROMPT_CHARS", 4000),
            confirm_writes=_bool("CONFIRM_WRITES", True),
            mcp_read_only=_bool("MCP_READ_ONLY", False),
            mcp_calls_per_minute=_int("MCP_CALLS_PER_MINUTE", 60),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
