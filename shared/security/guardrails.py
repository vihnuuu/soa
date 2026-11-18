import re
from collections.abc import Callable
from dataclasses import dataclass

_CONTROL = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"
)

_INJECTION_RULES: tuple[tuple[str, str], ...] = (
    (
        "override_instructions",
        r"\b(ignore|disregard|forget|override|bypass)\s+(?:(?:all|any|the|your|previous|prior|above|system)\s+)*"
        r"(?:instructions?|rules?|prompts?)\b",
    ),
    (
        "override_instructions_ua",
        r"(?:ігноруй|проігноруй|забудь|скасуй)\s+(?:(?:всі|усі|попередні)\s+)*(?:інструкції|правила|команди)",
    ),
    ("role_hijack", r"\byou\s+are\s+now\b|\bтепер\s+ти\b"),
    ("chat_markup", r"<\|?(?:im_start|im_end|system|assistant)\|?>|\[/?INST\]"),
    ("tool_call_spoof", r"<tool_call>"),
)
_COMPILED_RULES = tuple(
    (name, re.compile(pattern, re.IGNORECASE)) for name, pattern in _INJECTION_RULES
)


class GuardrailViolation(ValueError):
    pass


@dataclass(frozen=True)
class TextPolicy:
    field: str
    max_len: int = 255
    allow_empty: bool = False


Guardrail = Callable[[str, TextPolicy], str]


def strip_control(value: str) -> str:
    return _CONTROL.sub("", value)


def sanitize(value: str, policy: TextPolicy) -> str:
    return strip_control(value).strip()


def require_not_empty(value: str, policy: TextPolicy) -> str:
    if not value and not policy.allow_empty:
        raise GuardrailViolation(f"{policy.field} must not be empty")
    return value


def enforce_length(value: str, policy: TextPolicy) -> str:
    if len(value) > policy.max_len:
        raise GuardrailViolation(f"{policy.field} is too long (max {policy.max_len})")
    return value


def detect_injection(value: str) -> list[str]:
    return [name for name, rx in _COMPILED_RULES if rx.search(value)]


def reject_injection(value: str, policy: TextPolicy) -> str:
    if detect_injection(value):
        raise GuardrailViolation(f"{policy.field} contains instruction-like text")
    return value


DEFAULT_PIPELINE: tuple[Guardrail, ...] = (
    sanitize,
    require_not_empty,
    enforce_length,
    reject_injection,
)


def run_pipeline(
    value: str,
    policy: TextPolicy,
    pipeline: tuple[Guardrail, ...] = DEFAULT_PIPELINE,
) -> str:
    for step in pipeline:
        value = step(value, policy)
    return value


def clean_text(value: str, *, field: str, max_len: int = 255) -> str:
    return run_pipeline(value, TextPolicy(field=field, max_len=max_len))
