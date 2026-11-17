"""Tutor citado y «Pregunta a BIOCORE» (2026-11-17, Art. I): la IA responde solo con la base firmada."""
from contextlib import contextmanager
from pathlib import Path

import pytest

import educational.citation_tutor as tutor
import educational.knowledge_base as kb


class FakeClient:
    """Imita la interfaz que usa el narrador: `client.messages.stream(...)` con `text_stream`."""

    def __init__(self, texto="La RMSSD está más influida por el parasimpático [SG2017].", allows_personal_data=True):
        self.texto, self.allows_personal_data, self.llamadas = texto, allows_personal_data, []
        self.provider_name = "Proveedor de prueba"
        self.messages = self

    @contextmanager
    def stream(self, **kwargs):
        self.llamadas.append(kwargs)

        class _S:
            text_stream = iter([self.texto])
        yield _S()


def test_sin_fragmentos_firmados_no_se_llama_al_modelo():
    client = FakeClient()
    prep = tutor.preparar("tratamiento de la diabetes")
    assert not prep.hay_respuesta
    assert "".join(tutor.responder(prep, client)) == kb.NO_DISPONIBLE
    assert client.llamadas == []


def test_una_pregunta_vacia_no_busca_ni_llama():
    client = FakeClient()
    assert "".join(tutor.responder(tutor.preparar("   "), client)) == kb.NO_DISPONIBLE
    assert client.llamadas == []


def test_el_modelo_recibe_las_reglas_los_fragmentos_y_las_restricciones():
    client = FakeClient()
    prep = tutor.preparar("razón LF/HF")
    assert "".join(tutor.responder(prep, client)) == client.texto
    llamada = client.llamadas[0]
    assert llamada["system"] == tutor.SYSTEM_PROMPT
    contenido = llamada["messages"][0]["content"]
    assert "[B2013]" in contenido and "razón LF/HF (interpretación discutida)" in contenido
    assert contenido.endswith("Pregunta del estudiante:\nrazón LF/HF")


def test_el_nivel_gratuito_no_recibe_preguntas_escritas_por_personas():
    from domain.physiology.narrator.errors import ProviderNotAllowedError

    client = FakeClient(allows_personal_data=False)
    with pytest.raises(ProviderNotAllowedError):
        "".join(tutor.responder(tutor.preparar("razón LF/HF"), client))
    assert client.llamadas == []


def test_una_clave_inventada_se_avisa():
    prep = tutor.preparar("razón LF/HF")
    v = tutor.verificar_citas("Mide el balance autonómico [TF1996] [B2013].", prep)
    assert v.claves_inventadas == ["TF1996"]
    assert "[TF1996]" in v.avisos[0]


def test_una_respuesta_sin_citas_se_avisa_y_una_bien_citada_no():
    prep = tutor.preparar("razón LF/HF")
    assert tutor.verificar_citas("La razón LF/HF es discutida.", prep).avisos == [tutor.AVISO_SIN_CITAS]
    assert tutor.verificar_citas("Es discutida [B2013][SG2017].", prep).avisos == []


def test_la_base_se_reconstruye_cuando_cambia_un_documento_firmado(tmp_path):
    doc = tmp_path / "teoria.md"
    plantilla = ("# P\n\n**Estado:** FIRMADO\n\n## B1. HRV\n\n**Idea.** {texto} [SG2017].\n\n## Bibliografía\n\n"
                 "- **[SG2017]** Shaffer F. 2017.\n\n## Hoja de firma\n\n| B1 | HRV | ☑ |\n")
    doc.write_text(plantilla.format(texto="La HRV varía"), encoding="utf-8")
    db = tmp_path / "c.db"
    kb.asegurar_base(db_path=db, corpus=[doc])
    antes = db.stat().st_mtime_ns
    kb.asegurar_base(db_path=db, corpus=[doc])
    assert db.stat().st_mtime_ns == antes                     # sin cambios, no se reconstruye
    doc.write_text(plantilla.format(texto="La entropía muestral mide regularidad"), encoding="utf-8")
    kb.asegurar_base(db_path=db, corpus=[doc])
    assert kb.buscar("entropía", db_path=db)                   # el texto nuevo ya está en la base


def test_la_pagina_sin_ia_muestra_los_fragmentos_firmados(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=60)
    at.session_state["biocore_start_page"] = "pregunta"
    at.run()
    at.text_area(key="ask_biocore_question").input("¿Por qué se filtra el EMG a 20 Hz?").run()
    at.button(key="ask_biocore_submit").click().run()
    assert at.exception == []
    textos = " ".join(m.value for m in at.main.markdown)
    assert "artefacto de movimiento" in textos and "[DL2010]" in textos

    at.text_area(key="ask_biocore_question").input("tratamiento de la diabetes").run()
    at.button(key="ask_biocore_submit").click().run()
    assert any(kb.NO_DISPONIBLE in i.value for i in at.info)
