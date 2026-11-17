"""Calibración de la confianza (2026-11-17, Art. I): veredictos solo con el intervalo de Wilson, sin umbrales inventados."""
import ast
from pathlib import Path

import pytest

import educational.confidence_calibration as cc
from educational.quiz_bank import ACADEMIA_QUESTIONS, CONCEPT_BY_PROMPT, ECG12_QUESTIONS, EMG_QUESTIONS, HRV_QUESTIONS


def _r(correct, confidence, concept="hrv", item="x"):
    return {"item_id": item, "source": "quiz", "concept": concept, "correct": correct, "confidence": confidence}


def test_wilson_coincide_con_el_valor_de_referencia():
    bajo, alto = cc.wilson(8, 10)
    assert round(bajo, 3) == 0.490 and round(alto, 3) == 0.943


def test_sin_confianza_declarada_no_hay_veredicto():
    c = cc.calibrar([_r(True, None), _r(False, None)])
    assert not c.hay_datos and c.sin_confianza == 2
    assert cc.frase(c.total).startswith("No disponible")


def test_pocas_respuestas_no_bastan_para_etiquetar():
    c = cc.calibrar([_r(False, 100), _r(True, 50), _r(True, 75)])
    assert c.total.veredicto == cc.CALIBRADA       # el intervalo es tan ancho que no se puede afirmar nada


def test_exceso_y_falta_de_confianza_solo_fuera_del_intervalo():
    exceso = cc.calibrar([_r(i < 3, 100) for i in range(20)]).total
    falta = cc.calibrar([_r(True, 25) for _ in range(12)]).total
    assert exceso.veredicto == cc.EXCESO and exceso.confianza_media > exceso.intervalo[1]
    assert falta.veredicto == cc.FALTA and falta.confianza_media < falta.intervalo[0]


def test_por_concepto_por_nivel_y_errores_mas_seguros():
    c = cc.calibrar([_r(False, 75, "ritmo_y_conduccion", "a"), _r(False, 100, "news2", "b"),
                     _r(True, 50, "news2", "c"), _r(True, None, "news2", "d")])
    assert set(c.por_concepto) == {"ritmo_y_conduccion", "news2"}
    assert {n: g.n for n, g in c.por_nivel.items()} == {50: 1, 75: 1, 100: 1}
    assert [r["item_id"] for r in c.errores_mas_seguros] == ["b", "a"]
    assert c.sin_confianza == 1


def _conceptos_del_contrato():
    """`CONCEPTS` de `app/utils/session_learning.py`, leído sin importar Streamlit."""
    arbol = ast.parse(Path("app/utils/session_learning.py").read_text(encoding="utf-8"))
    nodo = next(n for n in arbol.body if isinstance(n, ast.Assign) and n.targets[0].id == "CONCEPTS")
    return set(ast.literal_eval(nodo.value))


def test_cada_pregunta_mapeada_existe_y_usa_el_vocabulario_de_luis():
    # 2026-11-17: también los bancos de EMG y HRV (firmados), con `emg`/`hrv`; y `QUIZ_BANKS` los cubre.
    enunciados = {q.prompt for q in ACADEMIA_QUESTIONS + ECG12_QUESTIONS + EMG_QUESTIONS + HRV_QUESTIONS}
    assert set(CONCEPT_BY_PROMPT) <= enunciados
    assert all(CONCEPT_BY_PROMPT[q.prompt] == "emg" for q in EMG_QUESTIONS)
    assert all(CONCEPT_BY_PROMPT[q.prompt] == "hrv" for q in HRV_QUESTIONS)
    arbol = ast.parse(Path("app/utils/confidence.py").read_text(encoding="utf-8"))
    nodo = next(n for n in arbol.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "QUIZ_BANKS")
    assert set(ast.literal_eval(nodo.value)) == {"academia", "ecg12", "emg", "hrv"}
    assert set(CONCEPT_BY_PROMPT.values()) <= _conceptos_del_contrato()
    assert set(cc.CONCEPT_LABELS) == _conceptos_del_contrato()


def test_el_desafio_ecg_registra_la_confianza_y_el_panel_la_compara():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=60)
    at.session_state["biocore_start_page"] = "desafio-ecg"
    at.run()
    assert "No disponible" in " ".join(m.value for m in at.main.markdown)
    q = ECG12_QUESTIONS[0]
    assert q.prompt in CONCEPT_BY_PROMPT
    confianza = at.radio(key="practicar_ecglab_12_confidence_1")
    assert confianza.value is None                      # sin confianza por defecto (Art. I)
    at.radio(key="practicar_ecglab_12_quiz_1").set_value(next(o for o in q.display_choices() if not q.is_correct(o)))
    confianza.set_value(100).run()
    at.button(key="practicar_ecglab_12_quiz_verify").click().run()
    assert at.exception == []
    log = at.session_state["session_learning_log"]
    assert len(log) == 1 and log[0]["confidence"] == 100 and log[0]["correct"] is False
    assert log[0]["concept"] == CONCEPT_BY_PROMPT[q.prompt] and log[0]["source"] == "quiz"
    textos = " ".join(m.value for m in at.main.markdown)
    assert "Con 1 respuesta" in textos and q.prompt in textos   # el error con más confianza muestra su enunciado
    at.button(key="practicar_ecglab_12_quiz_verify").click().run()
    assert len(at.session_state["session_learning_log"]) == 1   # verificar dos veces no duplica


def test_respiratorio_guarda_la_confianza_que_habia_al_responder():
    """Aquí la respuesta se corrige al elegirla: la confianza va antes, y cambiarla después no cuenta."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    from app.supermodules.respiratory_lab import views

    at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=60)
    at.session_state["biocore_start_page"] = "cuestionarios"
    at.run()
    tipo = "Diferenciación Apnea"
    next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value(tipo).run()
    confianza = at.radio(key=f"practicar_resp_quiz_{tipo}_confidence")
    assert confianza.value is None
    confianza.set_value(75).run()
    item = views.CONCEPT_QUIZ[tipo]
    mala = next(o for i, o in enumerate(item["options"]) if i != item["correct"])
    at.radio(key=f"practicar_resp_quiz_{tipo}").set_value(mala).run()
    assert at.exception == []
    log = at.session_state["session_learning_log"]
    assert len(log) == 1 and log[0]["concept"] == "respiracion_y_apnea" and log[0]["confidence"] == 75
    assert log[0]["correct"] is False
    at.radio(key=f"practicar_resp_quiz_{tipo}_confidence").set_value(25).run()   # ya con el resultado a la vista
    assert [r["confidence"] for r in at.session_state["session_learning_log"]] == [75]
    assert tipo in " ".join(m.value for m in at.main.markdown)                    # el error muestra su pregunta


def test_la_clave_de_wilson_en_pantalla_es_la_de_la_bibliografia():
    from app.supermodules.bibliography import METHODS

    ref = next(r for r in METHODS if r.key == cc.WILSON_KEY)
    assert "1927;22(158):209–212" in ref.text and "1927;22(158):209–212" in cc.WILSON_1927
    assert ("doi:10.1080/01621459.1927.10502953", "https://doi.org/10.1080/01621459.1927.10502953") in ref.links
    assert "intervalo de 95 % de Wilson [{cc.WILSON_KEY}]" in Path("app/utils/confidence.py").read_text(encoding="utf-8")
    assert f"[{cc.WILSON_KEY}] Wilson EB." in Path("THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


def test_el_concepto_del_cuestionario_respiratorio_es_del_vocabulario_de_luis():
    pytest.importorskip("streamlit")
    from app.supermodules.respiratory_lab import views

    assert views.QUIZ_CONCEPT == "respiracion_y_apnea" and views.QUIZ_CONCEPT in _conceptos_del_contrato()
