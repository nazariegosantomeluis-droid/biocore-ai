"""Configuración común de las pruebas.

El narrador detecta solo una IA local gratuita (Ollama en 127.0.0.1:11434).
Para que las pruebas den el mismo resultado en cualquier computadora -- con
o sin Ollama abierto -- se apunta la IA local a un puerto donde no escucha
nadie. Las pruebas que necesitan un servidor local levantan uno propio y lo
configuran con `providers.configure(url=...)`.
"""
import pytest


@pytest.fixture(autouse=True)
def _no_local_ai_by_default(monkeypatch):
    from domain.physiology.narrator import providers

    monkeypatch.setenv("BIOCORE_LOCAL_AI_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("BIOCORE_AI_PROVIDER", raising=False)
    monkeypatch.delenv("BIOCORE_LOCAL_AI_MODEL", raising=False)
    providers.configure()
    providers._probe_cache.clear()
    yield
    providers.configure()
    providers._probe_cache.clear()
