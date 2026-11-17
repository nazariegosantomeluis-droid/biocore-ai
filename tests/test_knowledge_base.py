"""Base de conocimiento de la IA (2026-11-17, Art. I): solo lo firmado, todo con cita, «no disponible» si no hay nada."""
from pathlib import Path

import pytest

import educational.knowledge_base as kb


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("kb") / "conocimiento.db"
    kb.construir(db_path=ruta)
    return ruta


def _doc(tmp_path: Path, estado="FIRMADO por Luis", marca="☑", cuerpo="**Idea.** La HRV varía entre latidos [SG2017].") -> Path:
    ruta = tmp_path / "teoria_prueba.md"
    ruta.write_text(
        f"# Prueba\n\n**Estado:** {estado}\n\n## B1. Qué es la HRV\n\n{cuerpo}\n\n"
        "## Bibliografía\n\n- **[SG2017]** Shaffer F, Ginsberg JP. 2017.\n\n"
        f"## Hoja de firma\n\n| # | Tema | Decisión |\n|---|---|---|\n| B1 | Qué es la HRV | {marca} firmado |\n",
        encoding="utf-8")
    return ruta


def test_los_documentos_firmados_no_tienen_afirmaciones_sin_cita_ni_claves_sueltas():
    for ruta in kb.CORPUS:
        doc = kb.leer_documento(ruta)
        assert doc.firmado, f"{ruta.name} debería estar firmado"
        assert kb.validar(doc) == []


def test_todos_los_temas_firmados_entran(base):
    import sqlite3
    con = sqlite3.connect(base)
    temas = {(d, t) for d, t in con.execute("SELECT DISTINCT documento, tema_id FROM fragmentos")}
    assert len({t for d, t in temas if d == "teoria_citada.md"}) == 10
    assert len({t for d, t in temas if d == "teoria_citada_2.md"}) == 18


def test_un_borrador_no_alimenta_a_la_ia(tmp_path):
    resumen = kb.construir(db_path=tmp_path / "b.db", corpus=[_doc(tmp_path, estado="BORRADOR, sin firmar")])
    assert resumen["fragmentos"] == 0
    assert kb.buscar("HRV", db_path=tmp_path / "b.db") == []


def test_un_tema_sin_palomear_no_entra(tmp_path):
    resumen = kb.construir(db_path=tmp_path / "t.db", corpus=[_doc(tmp_path, marca="☐")])
    assert resumen["fragmentos"] == 0


def test_una_afirmacion_sin_cita_impide_construir(tmp_path):
    with pytest.raises(kb.BaseInvalidaError, match="sin cita"):
        kb.construir(db_path=tmp_path / "x.db", corpus=[_doc(tmp_path, cuerpo="**Idea.** La HRV varía entre latidos.")])


def test_una_clave_sin_referencia_impide_construir(tmp_path):
    with pytest.raises(kb.BaseInvalidaError, match=r"\[XX2020\]"):
        kb.construir(db_path=tmp_path / "y.db", corpus=[_doc(tmp_path, cuerpo="**Idea.** Algo [XX2020].")])


def test_razon_lf_hf_trae_su_cita_y_la_restriccion_de_luis(base):
    resultados = kb.buscar("razón LF/HF", db_path=base)
    assert resultados[0]["tema_id"] == "B3"
    assert "B2013" in resultados[0]["claves"]
    assert resultados[0]["referencias"]["B2013"].startswith("Billman GE")
    contexto = kb.contexto_para_ia("razón LF/HF", db_path=base)
    assert "razón LF/HF (interpretación discutida)" in contexto
    assert "Restricciones firmadas por Luis" in contexto


def test_lo_que_no_tiene_fuente_se_declara_asi(base):
    resultados = kb.buscar("postura", db_path=base)
    assert resultados and resultados[0]["capa"] == "sin_fuente"
    assert "SIN FUENTE VERIFICADA" in kb.contexto_para_ia("efecto de la postura en la HRV", db_path=base)


def test_sin_fragmentos_firmados_la_respuesta_es_no_disponible(base):
    assert kb.buscar("tratamiento de la diabetes", db_path=base) == []
    assert kb.contexto_para_ia("tratamiento de la diabetes", db_path=base) is None


def test_la_busqueda_ignora_acentos(base):
    assert kb.buscar("normalizacion", db_path=base)[0]["tema_id"] == "A6"


@pytest.mark.parametrize("consulta", ['"', "LF/HF AND NOT", "*", "(", "", "¿?"])
def test_consultas_raras_no_rompen_la_busqueda(base, consulta):
    kb.buscar(consulta, db_path=base)


def test_un_comentario_sobre_biocore_no_se_atribuye_a_la_fuente():
    doc = kb.leer_documento(kb.CORPUS[0])
    nota = next(f for f in doc.fragmentos if f.texto.startswith("Por qué BIOCORE no calcula el total"))
    assert nota.capa == "nota" and nota.claves == []


def test_la_base_por_defecto_esta_aislada_en_la_suite():
    assert "conocimiento_suite" in str(kb.DEFAULT_DB_PATH)


# ── Sinónimos (2026-11-17) ──────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("consulta,tema", [
    ("electromiografía", "A1"),                              # la teoría dice «EMG»
    ("variabilidad de la frecuencia cardiaca", "B1"),        # la teoría dice «HRV»; no debe ganar el tema 2 (FC)
    ("¿qué mide la variabilidad cardíaca?", "B1"),
    ("frecuencia cardiaca normal", "2"),                     # sin «variabilidad», sigue siendo el tema 2
    ("CVM con dolor", "A6"),                                 # la teoría dice «contracción voluntaria isométrica máxima»
    ("saturación de oxígeno NEWS2", "6"),                    # la teoría dice «SpO₂»
    ("infarto en la descendente anterior", "5"),
    ("diafonía", "A8"),
])
def test_los_sinonimos_encuentran_lo_que_la_teoria_escribe_de_otro_modo(base, consulta, tema):
    assert kb.buscar(consulta, db_path=base)[0]["tema_id"] == tema


def test_ningun_termino_esta_en_dos_grupos_de_sinonimos():
    vistos = {}
    for i, grupo in enumerate(kb.SINONIMOS):
        for termino in grupo:
            clave = kb._normalizar(termino)
            assert vistos.setdefault(clave, i) == i, f"«{termino}» está en dos grupos"


def test_cada_grupo_de_sinonimos_nombra_algo_que_esta_en_la_teoria_firmada(base):
    import sqlite3
    filas = sqlite3.connect(base).execute("SELECT texto || ' ' || tema_titulo || ' ' || subtema FROM fragmentos")
    texto = " " + kb._normalizar(" ".join(t for (t,) in filas)) + " "     # lo mismo que indexa la búsqueda
    for grupo in kb.SINONIMOS:
        assert any(f" {kb._normalizar(t)} " in texto for t in grupo), grupo


def test_los_sinonimos_no_inventan_respuestas(base):
    assert kb.buscar("tratamiento de la diabetes", db_path=base) == []
    assert kb.contexto_para_ia("hipotiroidismo", db_path=base) is None


# ── Preguntas de la demo de «Pregunta a BIOCORE» (2026-11-17) ───────────────────────────────────────────────────────
@pytest.mark.parametrize("pregunta,tema", [
    ("¿por qué se filtra el EMG a 20 Hz?", "A4"),
    ("¿qué mide la electromiografía de superficie?", "A1"),
    ("¿qué es la variabilidad de la frecuencia cardiaca?", "B1"),
    ("¿la razón LF/HF mide el equilibrio simpático-vagal?", "B3"),
    ("¿cómo se calcula el NEWS2?", "6"),
    ("¿qué es la respiración de Cheyne-Stokes?", "7"),
    ("¿qué es la RMSSD?", "B2"),
    ("QUE MIDE LA ELECTROMIOGRAFIA DE SUPERFICIE", "A1"),         # sin acentos y en mayúsculas
])
def test_las_preguntas_de_la_demo_traen_un_fragmento_firmado_de_su_tema(base, pregunta, tema):
    assert tema in [r["tema_id"] for r in kb.buscar(pregunta, db_path=base)]


def test_una_pregunta_fuera_de_la_teoria_sigue_sin_fragmentos(base):
    assert kb.buscar("¿cuál es la capital de Francia?", db_path=base) == []
    assert kb.contexto_para_ia("¿cuál es la capital de Francia?", db_path=base) is None
