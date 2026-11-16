"""Errores del narrador, en un módulo aparte para que `client.py` y `privacy.py` los compartan sin importarse entre sí
(2026-11-16)."""


class NarratorNotConfiguredError(RuntimeError):
    """No hay con qué llamar al modelo: falta la clave (ANTHROPIC_API_KEY o la de la sesión)."""


class ProviderNotAllowedError(NarratorNotConfiguredError):
    """El proveedor elegido no puede recibir estos datos (p.ej. el nivel gratuito de Gemini con datos de una
    persona). Hereda de `NarratorNotConfiguredError` para que todo llamador que ya la atiende muestre el motivo."""
