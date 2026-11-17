"""Caso guiado de ECG 2: elevación del ST en V1–V4 (2026-11-17), FIRMADO por Luis el 2026-11-17.

Lo mismo que se exige al caso 1: las premisas salen de la medición, cada texto del código está en el documento, cada
línea citada existe literal, la correcta nunca es la opción más larga, y la página no lo muestra sin firma.
"""
import re
from pathlib import Path

import pytest

import educational.guided_case as g1
import educational.guided_case_anterior as g
from educational.guided_case import Estado

T1 = Path("docs/contenido/teoria_citada.md").read_text(encoding="utf-8").splitlines()
DOC = g.CASE_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def data():
    return g.build_case_data()


def _desafios(data):
    out = []
    for op in range(4):
        for pruebas in ((), ("st_i_avl",)):
            e = Estado()
            for pid in pruebas:
                g.pedir_prueba(e, data, pid, g.PRUEBA[pid].motivo_correcto)
            g.responder(e, "hipotesis_final", g.DECISION["hipotesis_final"].opciones[op], None)
            out.append(g.desafio(e, data))
    return out


def test_esta_firmado_con_su_hoja():
    assert DOC.splitlines()[2].startswith("**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome")
    assert "> Firmo el caso guiado 2. — Luis Nazariego Santome, 17/11/2026" in DOC and "☐" not in DOC
    assert g.case_signed()


def test_cada_linea_citada_esta_literal_en_la_teoria_firmada():
    for n, fragment in g.SIGNED_LINES.items():
        assert fragment in T1[n - 1], n
        assert f"- **t1:{n}:** {T1[n - 1]}" in DOC, n
    for n in {int(n) for n in re.findall(r"t1:(\d+)", DOC)}:
        assert n in g.SIGNED_LINES, n


def test_las_premisas_salen_de_la_medicion(data):
    assert min(data.mm(v) for v in ("V1", "V2", "V3", "V4")) > 0                 # V1–V4 se elevan, V1 incluida (≠ t1:80)
    assert max(data.mm("V5"), data.mm("V6")) < min(data.mm("V3"), data.mm("V4"))  # no «sobre todo V3–V6» (t1:79)
    assert data.mm("I") <= 0                                                      # I no se eleva: t1:78 incompleto
    assert max(("V1", "V2", "V3", "V4", "V5", "V6", "II", "III", "aVF", "I", "aVL"), key=data.mm) in ("V2", "V3")


def test_todo_texto_del_codigo_esta_en_el_documento(data):
    texts = [d.pregunta for d in g.DECISIONES] + [o for d in g.DECISIONES for o in d.opciones]
    texts += [d.explicacion for d in g.DECISIONES] + [p.nombre for p in g.PRUEBAS]
    texts += [m for p in g.PRUEBAS for m in p.motivos] + [p.resultado(data) for p in g.PRUEBAS]
    texts += _desafios(data) + [c.evidencia for c in g.competencias(Estado())]
    for text in texts:
        assert text in DOC, text[:80]


def test_toda_frase_de_ensenanza_cita_w2009_y_no_rotula_paredes(data):
    for d in g.DECISIONES:
        assert d.linea is None or "[W2009]" in d.explicacion, d.id
    for text in _desafios(data):
        assert "[W2009]" in text
        assert not re.search(r"inferior|\bpared\b|\bcara\b", text, re.I), text


def test_la_correcta_nunca_es_la_opcion_mas_larga():
    for d in g.DECISIONES:
        assert max(d.opciones, key=len) != d.correcta, d.id
        assert len(set(d.opciones)) == 4
    for p in g.PRUEBAS:
        assert max(p.motivos, key=len) != p.motivo_correcto, p.id


def test_recorrido_ideal_logra_todas_las_competencias(data):
    e = Estado()
    for did in ("grupo", "hipotesis_inicial"):
        g.responder(e, did, g.DECISION[did].correcta, 75)
    for pid in ("st_v1", "st_i_avl", "st_v5_v6"):
        g.pedir_prueba(e, data, pid, g.PRUEBA[pid].motivo_correcto)
    g.responder(e, "hipotesis_final", g.DECISION["hipotesis_final"].correcta, 75)
    g.responder(e, "limite", g.DECISION["limite"].correcta, 75)
    assert all(c.lograda for c in g.competencias(e))


def _page():
    from app.supermodules.academia.guided_case_view import render_guided_case
    render_guided_case()


def test_sin_firma_solo_se_ve_el_caso_1_y_se_dice_que_falta_uno(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(g, "case_signed", lambda doc=None: False)    # simula que el caso 2 no estuviera firmado
    at = AppTest.from_function(_page, default_timeout=60)
    at.run()
    assert at.exception == []
    assert not any(s.key == "guided_case_pick" for s in at.selectbox)
    assert any("1 caso(s) más pendiente(s) de firma" in c.value for c in at.caption)
    assert at.session_state["guided_case_id"] == g1.CASE_ID


def test_firmado_se_elige_en_la_pagina_y_registra_con_su_id():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_page, default_timeout=60)
    at.run()
    at.selectbox(key="guided_case_pick").set_value(g.CASE_ID).run()
    assert at.exception == []
    attempt = at.session_state["guided_case_attempt"]
    at.radio(key=f"guided_grupo_{attempt}").set_value("V1–V4").run()
    at.button(key="guided_grupo_submit").click().run()
    assert at.exception == []
    log = at.session_state["session_learning_log"]
    assert log[-1]["item_id"] == "caso_guiado:st_v1_v4:grupo" and log[-1]["correct"] is True
    assert log[-1]["source"] == "caso_guiado" and log[-1]["concept"] == "derivaciones_e_isquemia"


def test_en_la_app_aparecen_los_dos_casos_sin_aviso_de_firma_pendiente():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=240)
    at.session_state["biocore_start_page"] = "caso-guiado"
    at.run()
    assert at.exception == []
    pick = at.selectbox(key="guided_case_pick")
    assert list(pick.options) == ["Elevación del ST en II, III y aVF", "Elevación del ST en V1–V4"]
    assert not any("pendiente" in c.value and "firma" in c.value for c in at.caption)
