"""T5 de la ruta integrada (2026-11-18): navegación nueva y retiro de páginas del menú.

Diseño firmado, «Navegación nueva (T5)»: el menú baja de 32 páginas a cinco destinos (Hoy, Ruta, Paciente, Biblioteca
y Ajustes). Ninguna dirección vieja se rompe: cada página sigue abriendo en su `url_path`, dice en qué destino vive y
ese destino la enlaza (anti-meta: «una función que nadie puede alcanzar después del cambio de menú»). Visto bueno de
Luis: «sigue con T5» (2026-11-18).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path("app/main.py").resolve())

# La tabla del diseño: destino → las páginas de hoy que absorbe.
DESIGN = {
    "inicio": [],
    "ruta": ["quiz", "caso-ciego", "desafio-ecg", "caso-guiado", "cuestionarios", "casos-simulador", "what-if",
             "detective", "mi-sesion"],
    "paciente": ["gemelo", "ecg", "multisensor", "respiratorio", "eeg", "emg", "hrv", "biomarcadores", "calculadoras",
                 "pacientes", "comparar", "modelo-3d"],
    "biblioteca": ["temas", "teoria", "referencias", "ecg-3d", "bibliografia", "pregunta"],
    "ajustes": ["terminos", "privacidad"],
}
ABSORBED = sorted(u for urls in DESIGN.values() for u in urls)


def _open(url, **state):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _links(at):
    return [(e.proto.page, e.proto.label) for e in at.main.get("page_link")]


def test_el_menu_son_cinco_destinos():
    import app.main as m

    assert [url for url, _title in m.DESTINATIONS] == ["inicio", "ruta", "paciente", "biblioteca", "ajustes"]
    assert [title for _url, title in m.DESTINATIONS] == ["Hoy", "Ruta", "Paciente", "Biblioteca", "Ajustes"]
    visible = [url for _s, url, *_ in m._page_specs() if m.is_destination(url)]
    assert visible == ["inicio", "ruta", "paciente", "biblioteca", "ajustes"]
    titles = " ".join(t for _, _, t, _, _ in m._page_specs()).lower()
    assert "progreso" not in titles and "docente" not in titles          # siguen fuera hasta que haya identidad


def test_cada_pagina_de_hoy_vive_en_el_destino_del_diseno():
    import app.main as m

    for dest, urls in DESIGN.items():
        for url in urls:
            assert m.DESTINATION_OF[url] == dest, url
    assert sorted(m.DESTINATION_OF) == sorted(ABSORBED + list(DESIGN))


@pytest.mark.parametrize("url", ABSORBED)
def test_cada_direccion_vieja_sigue_abriendo_y_dice_donde_vive(url):
    import app.main as m

    at = _open(url)
    dest = m.DESTINATION_OF[url]
    title = dict(m.DESTINATIONS)[dest]
    assert any(page == dest and label.startswith(title) for page, label in _links(at)), (url, _links(at)[:3])


@pytest.mark.parametrize("dest,state", [("ruta", {"ruta_mode": "practica"}), ("paciente", {}), ("biblioteca", {}),
                                        ("ajustes", {})])
def test_cada_destino_enlaza_todas_sus_paginas(dest, state):
    at = _open(dest, **state)
    linked = {page for page, _label in _links(at)}
    assert set(DESIGN[dest]) <= linked, sorted(set(DESIGN[dest]) - linked)


def test_paciente_empieza_por_el_paciente_activo():
    at = _open("paciente")
    text = " ".join(m.value for m in at.main.markdown)
    assert "Paciente activo" in text or "sin paciente" in text.lower()


def _buttons(at):
    return [b.label for b in at.main.button]


def _go_station(at, index):
    at.button(key=f"ruta_node_{index}").click().run()
    assert at.exception == [], at.exception


def test_hoy_dice_empezar_la_ruta_sin_avance():
    at = _open("inicio")
    assert "Empezar la Ruta: Unidad Corazón" in _buttons(at)


def test_la_ruta_recuerda_la_unidad_al_ir_a_practica_libre_y_volver():
    """Revisión final de la T5: Streamlit borra el estado de un control que no se dibuja; la unidad abierta se perdía
    al pasar por «Práctica libre» (o por Hoy) y la Ruta volvía a Corazón."""
    at = _open("ruta")
    at.radio(key="ruta_unit").set_value("respiracion").run()
    _go_station(at, 2)
    at.radio(key="ruta_mode").set_value("practica").run()
    at.run()
    at.radio(key="ruta_mode").set_value("unidades").run()
    assert at.radio(key="ruta_unit").value == "respiracion"
    assert at.session_state["ruta_progress"]["respiracion"]["station"] == 2


def test_hoy_continua_en_la_unidad_abierta_aunque_la_ruta_no_se_dibuje():
    at = _open("ruta")
    at.radio(key="ruta_unit").set_value("respiracion").run()
    _go_station(at, 2)
    # Ir a Hoy: en otra página el control `ruta_unit` no existe (Streamlit lo borra); queda el avance y la unidad abierta.
    hoy = _open("inicio", ruta_progress=at.session_state["ruta_progress"],
                ruta_open_unit=at.session_state["ruta_open_unit"])
    hoy.run()
    assert any(label.startswith("Continúa en: Unidad Respiración · estación 2") for label in _buttons(hoy)), \
        _buttons(hoy)


def test_la_ruta_tiene_unidades_y_practica_libre():
    at = _open("ruta")
    assert at.radio(key="ruta_mode").options == ["Unidades", "Práctica libre"]
    assert at.radio(key="ruta_unit")                                    # por defecto, las unidades


def test_las_tarjetas_de_paciente_y_biblioteca_no_prometen_de_mas():
    """Revisión final de la T5 (Art. I): no todo instrumento escribe al paciente, ni toda la Biblioteca es firmada."""
    from app.supermodules import hubs

    at = _open("paciente")
    text = " ".join(c.value for c in at.main.caption)
    assert "Todo lo de aquí lee y escribe" not in text and "Guardar al gemelo" in text
    assert any("demostración" in d for _h, cards in hubs.PATIENT_GROUPS for url, d in cards if url == "multisensor")
    at = _open("biblioteca")
    assert "Solo contenido firmado" not in " ".join(c.value for c in at.main.caption)


def test_el_boton_de_hoy_abre_la_ruta_en_esa_unidad():
    at = _open("ruta")
    at.radio(key="ruta_unit").set_value("cerebro").run()
    _go_station(at, 3)
    hoy = _open("inicio", ruta_progress=at.session_state["ruta_progress"], ruta_open_mode="practica",
                ruta_open_unit=at.session_state["ruta_open_unit"])
    hoy.button(key="bc_continue").click().run()
    assert hoy.exception == [], hoy.exception
    assert hoy.radio(key="ruta_mode").value == "unidades" and hoy.radio(key="ruta_unit").value == "cerebro"


def test_un_enlace_fuera_de_la_app_dice_en_que_destino_esta():
    def _script():
        from app.utils import navigation as nav
        nav.SECTION_OF["calculadoras"] = "Paciente"
        nav.link("calculadoras", "Calculadora")

    at = AppTest.from_function(_script)
    at.run()
    assert "en el destino «Paciente» del menú lateral" in at.caption[0].value
