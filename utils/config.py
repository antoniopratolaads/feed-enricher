"""Persistenza configurazione (API keys, preferenze) su disco locale."""
from __future__ import annotations
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".feed_enricher"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "provider": "anthropic",          # anthropic | openai | gemini
    "anthropic_api_key": "",
    "anthropic_model": "claude-sonnet-4-6",
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "max_tokens": 3500,
    "temperature": 0.3,
    "max_workers": 5,
    "default_limit": 50,
}


def load_config() -> dict:
    cfg = DEFAULTS.copy()
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except Exception:
            pass
    # env override
    if os.getenv("ANTHROPIC_API_KEY"):
        cfg["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("OPENAI_API_KEY"):
        cfg["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        cfg["gemini_api_key"] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return cfg


def save_config(cfg: dict) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)  # solo owner read/write
    except Exception:
        pass
    return CONFIG_FILE


def clear_config() -> bool:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        return True
    return False


def mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return "—"
    return f"{key[:8]}...{key[-4:]}"


def test_anthropic(api_key: str, model: str = "claude-sonnet-4-6") -> tuple[bool, str]:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        r = client.messages.create(
            model=model, max_tokens=20,
            messages=[{"role": "user", "content": "Reply with just 'OK'"}],
        )
        return True, f"Risposta: {r.content[0].text.strip()[:30]}"
    except Exception as e:
        return False, str(e)[:200]


def test_openai(api_key: str, model: str = "gpt-4o-mini") -> tuple[bool, str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.chat.completions.create(
            model=model, max_tokens=20,
            messages=[{"role": "user", "content": "Reply with just 'OK'"}],
        )
        return True, f"Risposta: {r.choices[0].message.content.strip()[:30]}"
    except Exception as e:
        return False, str(e)[:200]


def test_gemini(api_key: str, model: str = "gemini-2.5-flash") -> tuple[bool, str]:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        r = client.models.generate_content(
            model=model,
            contents="Reply with just 'OK'",
            config={"max_output_tokens": 20, "temperature": 0.0},
        )
        return True, f"Risposta: {(r.text or '').strip()[:30]}"
    except Exception as e:
        return False, str(e)[:200]
