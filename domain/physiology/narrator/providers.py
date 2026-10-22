"""Motores de IA del narrador (2026-10-21): local y gratis, o Claude.

El narrador ya no exige una clave de API. Usa, en este orden (modo "auto"):

1. **IA local gratuita** -- un modelo de lenguaje abierto que corre en la
   propia computadora con Ollama (https://ollama.com) o con cualquier
   servidor compatible con la API de OpenAI (LM Studio, llama.cpp, vLLM,
   Jan...). Sin clave, sin costo y sin que los datos salgan del equipo:
   encaja con el Modo Rural. Se detecta solo en http://127.0.0.1:11434.
2. **Claude (Anthropic)**, si hay `ANTHROPIC_API_KEY`.

Sigue siendo IA real (Art. I): un modelo genera el texto a partir del
contexto estructurado del UPS o de las métricas del laboratorio, con las
mismas reglas de anclaje del system prompt. Si no hay ningún motor, el
narrador falla de forma explícita (`NarratorNotConfiguredError`): no existe
un texto de respaldo fingido.

Configuración (variables de entorno o `.env`, o el selector "Motor de IA"
de la barra lateral, que llama a `configure()`):
    BIOCORE_AI_PROVIDER     auto | local | anthropic        (por defecto: auto)
    BIOCORE_LOCAL_AI_URL    URL del servidor local          (por defecto: http://127.0.0.1:11434)
    BIOCORE_LOCAL_AI_MODEL  modelo local a usar             (por defecto: el primero instalado)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

DEFAULT_LOCAL_URL = "http://127.0.0.1:11434"
# Sugerencias para la guía de instalación (no se descargan solas).
SUGGESTED_LOCAL_MODELS = ("qwen2.5:7b", "llama3.1:8b", "gemma2:9b", "qwen2.5:3b")
PROVIDERS = ("auto", "local", "anthropic")
PROVIDER_LABELS = {"auto": "Automático", "local": "IA local gratis", "anthropic": "Claude (Anthropic)"}
SPANISH_GUARD = ("\n\nResponde siempre en español, con frases claras. Usa solo los datos del mensaje del "
                 "usuario; si algo no está en ellos, dilo en vez de inventarlo.")

_SETTINGS: Dict[str, Optional[str]] = {"provider": None, "model": None, "url": None}
_PROBE_TTL_S = 15.0
_probe_cache: Dict[str, Tuple[float, Optional[str], Tuple[str, ...]]] = {}


@dataclass(frozen=True)
class EngineStatus:
    provider: str          # "local" | "anthropic" | "none"
    ready: bool
    model: str
    detail: str            # frase para la interfaz
    url: str = ""
    api: str = ""          # "ollama" | "openai" (solo local)

    @property
    def label(self) -> str:
        if self.provider == "local":
            return f"IA local ({self.model})"
        if self.provider == "anthropic":
            return f"Claude ({self.model})"
        return "sin motor de IA"


def configure(provider: Optional[str] = None, model: Optional[str] = None, url: Optional[str] = None) -> None:
    """Preferencias elegidas en la interfaz (tienen prioridad sobre el entorno)."""
    if provider is not None and provider not in PROVIDERS:
        raise ValueError(f"proveedor desconocido: {provider}")
    _SETTINGS.update(provider=provider, model=model or None, url=url or None)


def _setting(key: str, env: str, default: Optional[str]) -> Optional[str]:
    value = _SETTINGS.get(key)
    if value:
        return value
    return os.environ.get(env, "").strip() or default


def provider_preference() -> str:
    p = (_setting("provider", "BIOCORE_AI_PROVIDER", "auto") or "auto").lower()
    return p if p in PROVIDERS else "auto"


def local_url() -> str:
    return (_setting("url", "BIOCORE_LOCAL_AI_URL", DEFAULT_LOCAL_URL) or DEFAULT_LOCAL_URL).rstrip("/")


def _get_json(url: str, timeout: float) -> Optional[dict]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                                    timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def probe_local(url: Optional[str] = None, *, timeout: float = 0.8, fresh: bool = False) -> Tuple[Optional[str], Tuple[str, ...]]:
    """(api, modelos instalados) del servidor local, o (None, ()) si no hay.
    Se recuerda unos segundos para no consultar en cada recarga."""
    base = (url or local_url()).rstrip("/")
    now = time.monotonic()
    hit = _probe_cache.get(base)
    if hit and not fresh and now - hit[0] < _PROBE_TTL_S:
        return hit[1], hit[2]
    api, models = None, ()
    data = _get_json(f"{base}/api/tags", timeout)          # Ollama
    if data and isinstance(data.get("models"), list):
        api, models = "ollama", tuple(m.get("name", "") for m in data["models"] if m.get("name"))
    else:
        data = _get_json(f"{base}/v1/models", timeout)     # LM Studio, llama.cpp, vLLM...
        if data and isinstance(data.get("data"), list):
            api, models = "openai", tuple(m.get("id", "") for m in data["data"] if m.get("id"))
    _probe_cache[base] = (now, api, models)
    return api, models


def _anthropic_model() -> str:
    return os.environ.get("BIOCORE_CLAUDE_MODEL", "").strip() or "claude-opus-4-8"


def local_status() -> EngineStatus:
    url = local_url()
    api, models = probe_local(url)
    if api is None:
        return EngineStatus("local", False, "", f"No hay un servidor de IA local en {url}.", url)
    if not models:
        return EngineStatus("local", False, "", "El servidor local responde, pero no tiene modelos instalados.",
                            url, api)
    wanted = _setting("model", "BIOCORE_LOCAL_AI_MODEL", None)
    model = wanted if wanted in models else models[0]
    return EngineStatus("local", True, model, f"IA local gratis con {model}.", url, api)


def anthropic_status() -> EngineStatus:
    if os.environ.get("ANTHROPIC_API_KEY"):
        m = _anthropic_model()
        return EngineStatus("anthropic", True, m, f"Claude ({m}) con ANTHROPIC_API_KEY.")
    return EngineStatus("anthropic", False, _anthropic_model(), "No hay ANTHROPIC_API_KEY.")


def resolve() -> EngineStatus:
    """El motor que se usará ahora."""
    pref = provider_preference()
    if pref == "local":
        return local_status()
    if pref == "anthropic":
        return anthropic_status()
    loc = local_status()
    if loc.ready:
        return loc
    ant = anthropic_status()
    if ant.ready:
        return ant
    return EngineStatus("none", False, "", "Sin motor de IA: instala Ollama (gratis) o configura una clave.")


# ─────────────────────────────────────────────────────────────────────────
# Generación en streaming
# ─────────────────────────────────────────────────────────────────────────

def _post_stream(url: str, payload: dict, timeout: float = 300.0):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
                                 method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def stream_local(system: str, messages: List[dict], *, model: str, url: str, api: str,
                 max_tokens: int = 2048, temperature: float = 0.3) -> Iterator[str]:
    """Texto en fragmentos desde el servidor local (Ollama o compatible con OpenAI)."""
    msgs = [{"role": "system", "content": system + SPANISH_GUARD}] + [
        {"role": m["role"], "content": m["content"]} for m in messages]
    if api == "ollama":
        payload = {"model": model, "messages": msgs, "stream": True,
                   "options": {"temperature": temperature, "num_predict": max_tokens}}
        with _post_stream(f"{url}/api/chat", payload) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(f"IA local: {data['error']}")
                piece = (data.get("message") or {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break
        return
    payload = {"model": model, "messages": msgs, "stream": True, "max_tokens": max_tokens,
               "temperature": temperature}
    with _post_stream(f"{url}/v1/chat/completions", payload) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            data = json.loads(body)
            for choice in data.get("choices", []):
                piece = (choice.get("delta") or {}).get("content") or ""
                if piece:
                    yield piece


def stream_anthropic(system: str, messages: List[dict], *, model: str, max_tokens: int,
                     client=None) -> Iterator[str]:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    with client.messages.stream(model=model, max_tokens=max_tokens, system=system, messages=messages) as stream:
        yield from stream.text_stream


def stream_chat(system: str, messages: List[dict], *, max_tokens: int = 4096,
                anthropic_model: Optional[str] = None) -> Iterator[str]:
    """Genera con el motor activo; `NarratorNotConfiguredError` si no hay ninguno."""
    from .client import NarratorNotConfiguredError

    engine = resolve()
    if not engine.ready:
        raise NarratorNotConfiguredError(
            f"{engine.detail} Opción gratis: instala Ollama (https://ollama.com) y ejecuta "
            "`ollama pull qwen2.5:7b`; BIOCORE lo detecta solo. También puedes usar Claude con "
            "ANTHROPIC_API_KEY en el archivo .env. No hay una narración de respaldo simulada."
        )
    if engine.provider == "local":
        yield from stream_local(system, messages, model=engine.model, url=engine.url, api=engine.api,
                                max_tokens=min(max_tokens, 2048))
        return
    yield from stream_anthropic(system, messages, model=anthropic_model or engine.model, max_tokens=max_tokens)
