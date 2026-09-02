"""Utilities de UI pequeñas (wrappers seguros para Streamlit)."""
import streamlit as st


def safe_image(content, **kwargs):
    """Muestra `content` con `st.image` sólo si `content` no está vacío.

    - Si `content` es None, cadena vacía, lista vacía o similar, muestra una
      advertencia leve en lugar de lanzar excepción.
    - Acepta rutas, URLs, PIL images o listas (igual que `st.image`).
    """
    if not content:
        st.warning("No hay imagen disponible para mostrar.")
        return None

    try:
        return st.image(content, **kwargs)
    except Exception as e:
        st.error(f"Error mostrando la imagen: {e}")
        return None
