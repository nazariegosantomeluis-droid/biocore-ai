"""
Proveedor Gemini (Google) del narrador, por su API REST (2026-11-16).

Por qué existe: la API de Anthropic necesita una clave de pago y Gemini tiene un nivel gratuito (clave de Google AI
Studio). Se llama con la biblioteca estándar (`urllib`): no agrega dependencias.

- `GeminiClient` imita lo poco que el narrador usa del cliente de Anthropic: `client.messages.stream(model=...,
  max_tokens=..., system=..., messages=...)` usado como contexto con `.text_stream`. Así `stream_narration`,
  `stream_findings_narration` y `stream_causal_narration` lo usan igual que al de Anthropic.
- Petición: POST `{API_BASE}/models/{modelo}:streamGenerateContent?alt=sse`, con la clave en la cabecera
  `x-goog-api-key` (no en la URL, para que no quede en registros de proxies), `systemInstruction`, `contents` (rol
  `user` o `model`) y `generationConfig.maxOutputTokens`. La respuesta llega como eventos SSE `data: {...}` con el
  texto en `candidates[0].content.parts[].text`; las partes marcadas como razonamiento (`thought`) no se muestran.
- `allows_personal_data = False`: el nivel gratuito no recibe datos de personas (`privacy.py`).
- Modelo: Google cambia seguido los modelos del nivel gratuito. Al validar la clave (`validate_key`) se listan los
  que esa clave puede usar con `generateContent` y se elige el primero de `PREFERRED_MODELS`, o el primer «flash».

**No verificado por ejecución contra la API real**: en el entorno de desarrollo no hay clave de Google ni salida a
sus servidores. Las pruebas (`tests/test_narrator_gemini.py`) usan un transporte simulado con el formato de la API.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Tuple

__all__ = [
    "API_BASE",
    "PREFERRED_MODELS",
    "DEFAULT_GEMINI_MODEL",
    "GeminiError",
    "GeminiClient",
    "build_payload",
    "parse_sse",
    "list_models",
    "choose_model",
    "validate_key",
]

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED_MODELS = ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                    "gemini-2.5-flash")
DEFAULT_GEMINI_MODEL = PREFERRED_MODELS[0]
TIMEOUT_S = 60.0
VALIDATE_TIMEOUT_S = 15.0
_CUT_REASONS = {
    "MAX_TOKENS": "la respuesta llegó al límite de longitud",
    "SAFETY": "los filtros de seguridad de Google cortaron la respuesta",
    "RECITATION": "Google cortó la respuesta por parecerse a un texto publicado",
    "PROHIBITED_CONTENT": "los filtros de Google cortaron la respuesta",
    "BLOCKLIST": "los filtros de Google cortaron la respuesta",
    "SPII": "Google cortó la respuesta por contener datos personales",
}

Opener = Callable[..., object]          # urllib.request.urlopen o un doble de prueba con la misma firma


class GeminiError(RuntimeError):
    """Error de la API de Gemini, con un mensaje en español para la persona."""

    def __init__(self, message: str, status: Optional[int] = None, reason: Optional[str] = None) -> None:
        super().__init__(message)
        self.status, self.reason = status, reason


def _request(url: str, api_key: str, body: Optional[dict] = None) -> urllib.request.Request:
    headers = {"x-goog-api-key": api_key}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")


def _error_from_http(exc: urllib.error.HTTPError, model: Optional[str] = None) -> GeminiError:
    status, reason, detail = exc.code, None, ""
    try:
        payload = json.loads(exc.read().decode("utf-8", "replace") or "{}").get("error", {})
        detail = str(payload.get("message", ""))
        for item in payload.get("details", []) or []:
            reason = reason or item.get("reason")
    except (ValueError, AttributeError, OSError):
        pass
    if reason == "API_KEY_INVALID" or (status == 400 and "api key" in detail.lower()):
        message = "Google rechazó la clave: no es válida o fue revocada. Revisa que la copiaste completa."
    elif status == 403:
        message = "La clave no tiene permiso para usar la API de Gemini (o la API no está activada en su proyecto)."
    elif status == 404:
        message = f"El modelo {model or '?'} no está disponible para esta clave."
    elif status == 429:
        message = "Se acabó la cuota gratuita de Gemini por ahora (límite por minuto o por día). Intenta más tarde."
    else:
        message = f"Google respondió con un error ({status}) al llamar a Gemini. Intenta de nuevo."
    return GeminiError(message, status=status, reason=reason)


def build_payload(system: str, messages: Iterable[Dict[str, str]], max_tokens: int) -> dict:
    """Los mensajes al estilo de Anthropic (`role` user/assistant, `content` texto) en el formato de Gemini."""
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages]
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": int(max_tokens)},
    }


def _texts(event: dict) -> Iterator[str]:
    if "error" in event:
        message = str(event["error"].get("message", "error sin detalle"))
        raise GeminiError(f"Gemini devolvió un error a mitad de la respuesta: {message}")
    blocked = (event.get("promptFeedback") or {}).get("blockReason")
    if blocked:
        raise GeminiError(f"Google bloqueó la petición con sus filtros de seguridad ({blocked}).", reason=blocked)
    for candidate in event.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            if part.get("thought"):
                continue                                  # razonamiento interno del modelo: no es la respuesta
            if part.get("text"):
                yield part["text"]
        cut = _CUT_REASONS.get(candidate.get("finishReason", ""))
        if cut:
            yield f"\n\n[Respuesta incompleta: {cut}.]"


def parse_sse(lines: Iterable[bytes]) -> Iterator[str]:
    """Texto de la respuesta, en orden, a partir de las líneas del flujo SSE (`data: {...}` y líneas en blanco)."""
    buffer: List[str] = []
    for raw in lines:
        line = raw.decode("utf-8", "replace").rstrip("\r\n") if isinstance(raw, bytes) else raw.rstrip("\r\n")
        if line.startswith("data:"):
            buffer.append(line[5:].lstrip())
        elif not line.strip() and buffer:
            yield from _texts(json.loads("\n".join(buffer)))
            buffer = []
    if buffer:
        yield from _texts(json.loads("\n".join(buffer)))


class _Stream:
    """Lo que devuelve `client.messages.stream(...)`: contexto con `.text_stream`, como el SDK de Anthropic."""

    def __init__(self, client: "GeminiClient", model: str, body: dict) -> None:
        self._client, self._model, self._body = client, model, body
        self._response = None

    def __enter__(self) -> "_Stream":
        url = f"{API_BASE}/models/{self._model}:streamGenerateContent?alt=sse"
        try:
            self._response = self._client.opener(_request(url, self._client.api_key, self._body),
                                                 timeout=self._client.timeout)
        except urllib.error.HTTPError as exc:
            raise _error_from_http(exc, self._model) from exc
        except urllib.error.URLError as exc:
            raise GeminiError("No se pudo conectar con Gemini. Revisa tu conexión a internet.") from exc
        return self

    @property
    def text_stream(self) -> Iterator[str]:
        return parse_sse(self._response)

    def __exit__(self, *exc_info) -> None:
        close = getattr(self._response, "close", None)
        if close is not None:
            close()


class _Messages:
    def __init__(self, client: "GeminiClient") -> None:
        self._client = client

    def stream(self, *, model: Optional[str] = None, max_tokens: int, system: str,
               messages: List[Dict[str, str]]) -> _Stream:
        return _Stream(self._client, model or self._client.model, build_payload(system, messages, max_tokens))


class GeminiClient:
    """Cliente del nivel gratuito de Gemini con la interfaz que usa el narrador."""

    provider = "gemini"
    provider_name = "Google Gemini (nivel gratuito)"
    allows_personal_data = False

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, opener: Optional[Opener] = None,
                 timeout: float = TIMEOUT_S) -> None:
        self.api_key = api_key
        self.model = model
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout
        self.messages = _Messages(self)

    @property
    def default_model(self) -> str:
        return self.model


def list_models(api_key: str, opener: Optional[Opener] = None, timeout: float = VALIDATE_TIMEOUT_S) -> List[str]:
    """Modelos que esta clave puede usar con `generateContent` (sin el prefijo `models/`)."""
    opener = opener or urllib.request.urlopen
    names: List[str] = []
    token = ""
    for _ in range(20):                                       # paginado; 20 páginas sobran
        url = f"{API_BASE}/models?pageSize=1000" + (f"&pageToken={token}" if token else "")
        try:
            response = opener(_request(url, api_key), timeout=timeout)
        except urllib.error.HTTPError as exc:
            raise _error_from_http(exc) from exc
        except urllib.error.URLError as exc:
            raise GeminiError("No se pudo conectar con Google para verificar la clave. Revisa tu conexión a "
                              "internet.") from exc
        payload = json.loads(response.read().decode("utf-8") or "{}")
        for model in payload.get("models") or []:
            if "generateContent" in (model.get("supportedGenerationMethods") or []):
                names.append(str(model.get("name", "")).split("/", 1)[-1])
        token = payload.get("nextPageToken") or ""
        if not token:
            break
    return names


def choose_model(available: Iterable[str]) -> Optional[str]:
    available = list(available)
    for preferred in PREFERRED_MODELS:
        if preferred in available:
            return preferred
    flash = [name for name in available if "flash" in name and "image" not in name and "tts" not in name]
    return flash[0] if flash else None


def validate_key(api_key: str, opener: Optional[Opener] = None) -> Tuple[Optional[str], Optional[str]]:
    """(modelo elegido, None) si la clave sirve; (None, motivo) si no."""
    try:
        model = choose_model(list_models(api_key, opener))
    except GeminiError as exc:
        return None, str(exc)
    if model is None:
        return None, "La clave es válida, pero no tiene ningún modelo «flash» de Gemini disponible para generar texto."
    return model, None
