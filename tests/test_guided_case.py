"""Caso guiado de ECG (2026-11-17, Art. I): contenido firmado, resultados medidos, desafío por reglas, nada sin firma.

Firmado por Luis el 2026-11-17 (`docs/contenido/caso_guiado_ecg.md`, sección 8) y montado en Practicar (`caso-guiado`)."""
import re
from pathlib import Path

import pytest

import educational.guided_case as g

T1 = Path("docs/contenido/teoria_citada.md").read_text(encoding="utf-8").splitlines()
DOC = g.CASE_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def data():
    return g.build_case_data()


def _textos_al_estudiante(data):
    textos = [d.pregunta for d in g.DECISIONES] + [o for d in g.DECISIONES for o in d.opciones]
    textos += [d.explicacion for d in g.DECISIONES] + [p.nombre for p in g.PRUEBAS]
    textos += [m for p in g.PRUEBAS for m in p.motivos] + [p.no_disponible for p in g.PRUEBAS]
    textos += [p.resultado(data) or "" for p in g.PRUEBAS]
    for op in range(4):
        for pruebas in ((), ("st_ii_iii",), ("st_i_avl",)):
            e = g.Estado()
            for pid in pruebas:
                g.pedir_prueba(e, data, pid, g.PRUEBA[pid].motivo_correcto)
            g.responder(e, "hipotesis_final", g.DECISION["hipotesis_final"].opciones[op], None)
            textos.append(g.desafio(e, data))
    return textos


def test_cada_linea_citada_esta_en_la_teoria_firmada():
    for n, fragmento in g.SIGNED_LINES.items():
        assert fragmento in T1[n - 1], n


def test_cada_t1_del_documento_existe_literal_en_teoria_citada():
    """La sección 2 copia cada línea citada; tiene que ser IDÉNTICA a esa línea de `teoria_citada.md`, y toda cita
    «t1:N» del documento (y del código) tiene que estar en esa lista."""
    copiadas = dict((int(n), texto) for n, texto in re.findall(r"(?m)^- \*\*t1:(\d+):\*\* (.*)$", DOC))
    assert copiadas and set(g.SIGNED_LINES) <= set(copiadas)
    for n, texto in copiadas.items():
        assert T1[n - 1] == texto, n
    citadas = {int(n) for n in re.findall(r"t1:(\d+)", DOC)}
    citadas |= {p.linea for p in g.PRUEBAS} | {d.linea for d in g.DECISIONES if d.linea}
    assert citadas <= set(copiadas), citadas - set(copiadas)


def test_las_premisas_del_caso_salen_de_la_medicion(data):
    assert data.mm("III") > data.mm("II") > 0 and data.mm("aVF") > 0         # elevación en II, III y aVF; III > II
    assert data.mm("I") < 0 and data.mm("aVL") < 0                            # sin elevación en I y aVL
    assert all(data.mm(v) == 0 for v in ("V1", "V2", "V3", "V4"))            # nada en V1–V4
    assert g.PRUEBA["v3r_v4r"].resultado(data) is None                        # sin derivaciones derechas


def test_lo_que_ve_el_estudiante_esta_en_el_documento_firmado(data):
    """Preguntas, opciones, motivos, explicaciones, resultados, desafíos, evidencias y textos de la pantalla."""
    from app.supermodules.academia.guided_case_view import INTRO

    textos = _textos_al_estudiante(data)
    textos += [c.evidencia for c in g.competencias(g.Estado())]
    textos += [INTRO, "Simulación: trazado construido por el simulador de 12 derivaciones; las pruebas muestran lo que "
                      "mide el analizador de BIOCORE sobre él."]
    for texto in filter(None, textos):        # "" = prueba sin texto de «no disponible»
        assert texto in DOC, texto


def test_ningun_texto_sin_linea_firmada_onda_delta_fuera(data):
    """La hoja de revisión sustituyó «Buscar una onda delta» (sin línea firmada) por distractores del tema 3."""
    for texto in _textos_al_estudiante(data):
        assert "onda delta" not in texto


def test_el_documento_esta_firmado_y_el_borrador_no_se_mostraria(tmp_path):
    assert DOC.splitlines()[2].startswith("**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome")
    assert "## 8. Firma" in DOC and "— Luis Nazariego Santome, 17/11/2026" in DOC
    assert g.case_signed()
    borrador = tmp_path / "borrador.md"
    borrador.write_text("# Caso\n\n**Estado:** BORRADOR, sin firmar\n", encoding="utf-8")
    assert not g.case_signed(borrador)
    firmado = tmp_path / "caso.md"
    firmado.write_text("# Caso\n\n**Estado:** FIRMADO por Luis Nazariego Santome\n", encoding="utf-8")
    assert g.case_signed(firmado)
    assert not g.case_signed(tmp_path / "no_existe.md")


def test_la_correcta_va_primero_y_no_se_repiten_opciones():
    for d in g.DECISIONES:
        assert len(set(d.opciones)) == len(d.opciones) == 4
    for p in g.PRUEBAS:
        assert len(set(p.motivos)) == len(p.motivos) == 3


def test_toda_frase_de_ensenanza_cita_w2009(data):
    for d in g.DECISIONES:
        assert (d.linea is None) or "[W2009]" in d.explicacion, d.id
    for texto in _textos_al_estudiante(data)[-12:]:                          # los desafíos
        assert "[W2009]" in texto, texto


def test_ninguna_derivacion_se_rotula_por_pared(data):
    """Decisión de Luis en el tema 5 (t1:70): las derivaciones se nombran por su nombre, no por pared."""
    for texto in _textos_al_estudiante(data):
        assert not re.search(r"inferior|\bpared\b|\bcara\b", texto, re.I), texto


def test_recorrido_ideal_logra_todas_las_competencias(data):
    e = g.Estado()
    g.responder(e, "grupo", g.DECISION["grupo"].correcta, 75)
    g.responder(e, "hipotesis_inicial", g.DECISION["hipotesis_inicial"].correcta, 50)
    for pid in ("st_ii_iii", "st_i_avl", "v3r_v4r"):
        g.pedir_prueba(e, data, pid, g.PRUEBA[pid].motivo_correcto)
    g.responder(e, "hipotesis_final", g.DECISION["hipotesis_final"].correcta, 75)
    assert "III (+2.9 mm) mayor que II (+2.1 mm)" in g.desafio(e, data)
    g.responder(e, "limite", g.DECISION["limite"].correcta, 75)
    assert all(c.lograda for c in g.competencias(e))
    assert [ev.tipo for ev in e.recorrido] == ["decision", "decision", "prueba", "prueba", "prueba", "decision",
                                               "desafio", "decision"]


def test_concluir_antes_del_dato_se_detecta_y_se_desafia(data):
    e = g.Estado()
    g.responder(e, "hipotesis_inicial", "La coronaria derecha, con seguridad", 100)
    g.pedir_prueba(e, data, "st_i_avl", "Medir el intervalo PR")                # motivo equivocado
    g.responder(e, "hipotesis_final", g.DECISION["hipotesis_final"].correcta, 100)
    assert "todavía no comparaste II con III" in g.desafio(e, data)
    g.pedir_prueba(e, data, "st_ii_iii", g.PRUEBA["st_ii_iii"].motivo_correcto)
    g.responder(e, "hipotesis_final", g.DECISION["hipotesis_final"].correcta, 75)  # ya con el dato
    logro = {c.nombre: c.lograda for c in g.competencias(e)}
    assert logro["Reconoce lo que el primer dato no permite decidir"] is False
    assert logro["Evita concluir antes de tener el dato"] is False             # cuenta la PRIMERA conclusión
    assert logro["Justifica cada prueba que pide"] is False
    assert logro["Actualiza la hipótesis con la nueva evidencia"] is True
    assert logro["Reconoce la información que falta"] is None                  # todavía no respondió «límite»


def test_el_desafio_a_la_circunfleja_muestra_la_evidencia_en_contra(data):
    e = g.Estado()
    g.pedir_prueba(e, data, "st_i_avl", g.PRUEBA["st_i_avl"].motivo_correcto)
    g.responder(e, "hipotesis_final", "Sugiere circunfleja", 75)
    texto = g.desafio(e, data)
    assert "descenso" in texto and "-1.8 mm" in texto


def test_opciones_y_motivos_desconocidos_se_rechazan(data):
    with pytest.raises(ValueError):
        g.responder(g.Estado(), "grupo", "otra cosa", None)
    with pytest.raises(ValueError):
        g.pedir_prueba(g.Estado(), data, "st_ii_iii", "porque sí")


def test_la_pantalla_firmada_lleva_el_caso_y_registra_la_confianza():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    def _script():
        from app.supermodules.academia.guided_case_view import render_guided_case
        render_guided_case()

    at = AppTest.from_function(_script, default_timeout=120)
    at.run()
    assert at.exception == []
    assert any("Simulación" in c.value for c in at.caption)
    at.radio(key="guided_grupo_1").set_value(g.DECISION["grupo"].correcta).run()
    at.radio(key="guided_grupo_confidence_1").set_value(75).run()
    at.button(key="guided_grupo_submit").click().run()
    assert at.exception == []
    log = at.session_state["session_learning_log"]
    assert log[-1]["source"] == "caso_guiado" and log[-1]["concept"] == "derivaciones_e_isquemia"
    assert log[-1]["confidence"] == 75 and log[-1]["correct"] is True
    assert log[-1]["item_id"] == "caso_guiado:st_ii_iii_avf:grupo"
    assert any("Correcto" in s.value for s in at.success)
    at.run()                                                                   # otra pasada: no se registra dos veces
    assert len(at.session_state["session_learning_log"]) == 1


def test_sin_firma_la_pantalla_solo_dice_que_falta_la_firma(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    import educational.guided_case_anterior as g2

    # AppTest corre en este proceso; se restaura solo. Ningún caso firmado (desde el 2026-11-17 hay dos).
    monkeypatch.setattr(g, "case_signed", lambda doc=None: False)
    monkeypatch.setattr(g2, "case_signed", lambda doc=None: False)

    def _script():
        from app.supermodules.academia.guided_case_view import render_guided_case
        render_guided_case()

    at = AppTest.from_function(_script, default_timeout=60)
    at.run()
    assert at.exception == [] and any("pendiente de firma" in i.value for i in at.info)
    assert not at.radio


def test_el_caso_aparece_en_su_pagina_de_practicar():
    """Montado donde dice la firma: Practicar, `caso-guiado`, después de `desafio-ecg`; con el documento FIRMADO la
    página muestra el caso (no el aviso de firma pendiente)."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    import app.main as m

    urls = [url for section, url, *_ in m._page_specs() if section == "Ruta"]       # T5: Practicar vive en la Ruta
    assert urls.index("caso-guiado") == urls.index("desafio-ecg") + 1

    at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=180)
    at.session_state["biocore_start_page"] = "caso-guiado"
    at.run()
    assert at.exception == []
    assert not any("pendiente de firma" in i.value for i in at.info)
    assert any(r.key == "guided_grupo_1" for r in at.radio)
    assert any("Simulación" in c.value for c in at.caption)
