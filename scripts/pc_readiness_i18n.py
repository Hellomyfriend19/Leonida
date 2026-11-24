"""Load UI strings for scripts/pc_readiness.py (stdlib only)."""
from __future__ import annotations

import json
import os

I18N_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n", "pc_readiness")
FALLBACK = "en"
KNOWN_ALIASES = {
    "de_de": "de",
    "de-at": "de",
    "de-ch": "de",
    "en_us": "en",
    "en_gb": "en",
    "en-us": "en",
    "en-gb": "en",
    "ru_ru": "ru",
}


class Messages:
    def __init__(self, table: dict[str, str], lang: str, resolved: str) -> None:
        self.lang = lang
        self.resolved = resolved
        self._table = table

    def t(self, key: str, **kwargs: object) -> str:
        text = self._table.get(key)
        if text is None:
            text = key
        if kwargs:
            return text.format(**kwargs)
        return text


def available_languages() -> list[str]:
    if not os.path.isdir(I18N_DIR):
        return [FALLBACK]
    out = sorted({os.path.splitext(name)[0] for name in os.listdir(I18N_DIR) if name.endswith(".json")})
    return out or [FALLBACK]


def normalize_lang(code: str) -> str | None:
    code = code.strip().replace("_", "-")
    if not code:
        return None
    lower = code.lower()
    if lower in KNOWN_ALIASES:
        return KNOWN_ALIASES[lower]
    for lang in available_languages():
        if lower == lang.lower():
            return lang
    base = lower.split("-", 1)[0]
    if base in KNOWN_ALIASES:
        return KNOWN_ALIASES[base]
    for lang in available_languages():
        if lang.lower().split("-", 1)[0] == base:
            return lang
    return None


def detect_language() -> str:
    """Default UI language is English unless LEONIDA_LANG is set."""
    env = os.environ.get("LEONIDA_LANG", "").strip()
    if env:
        return normalize_lang(env) or FALLBACK
    return FALLBACK


def load_messages(lang: str) -> Messages:
    requested = lang or FALLBACK
    resolved = normalize_lang(requested) or FALLBACK
    base = _read_table(FALLBACK)
    if not base:
        raise ValueError(f"missing master strings: {os.path.join(I18N_DIR, FALLBACK + '.json')}")
    if resolved != FALLBACK:
        overlay = _read_table(resolved)
        if not overlay:
            resolved = FALLBACK
        else:
            merged = {**base, **overlay}
            return Messages(merged, requested, resolved)
    return Messages(base, requested, resolved)


def _read_table(code: str) -> dict[str, str]:
    path = os.path.join(I18N_DIR, f"{code}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    bad = [k for k, v in data.items() if not isinstance(v, str)]
    if bad:
        raise ValueError(f"{path}: non-string values for {bad!r}")
    return data


def keys_in_master() -> set[str]:
    return set(_read_table(FALLBACK).keys())