"""T2 (2026-11-18): los laboratorios se vuelven instrumentos que una estación de la ruta puede montar.

Contrato (`app/instruments/base.py`): un `InstrumentContext` dice con qué prefijo se nombran las claves de los widgets
y dónde van los controles. En la página de siempre (`PAGE`) todo queda igual: mismas claves y controles en el menú
lateral. En una estación (`station_context`), las claves llevan el prefijo de la estación y los controles van en la
página, nunca en el menú lateral: así el mismo instrumento se puede montar dos veces sin chocar."""

from streamlit.testing.v1 import AppTest

from app.utils import ai_session as S


def test_page_usa_claves_de_siempre():
    from app.instruments.base import PAGE

    assert PAGE.k("hrv_lab_save_to_ups") == "hrv_lab_save_to_ups"
    assert PAGE.mode == "libre" and PAGE.controls is None


def _station_script():
    import streamlit as st

    from app.instruments.base import station_context

    ctx = station_context("corazon_e2")
    st.session_state["_clave"] = ctx.k("sel")
    st.session_state["_modo"] = ctx.mode
    ctx.panel.selectbox("Fuente", ["a", "b"], key=ctx.k("sel"))


def test_station_prefija_claves():
    at = AppTest.from_function(_station_script, default_timeout=60).run()
    assert not at.exception, at.exception
    assert at.session_state["_clave"] == "corazon_e2__sel"
    assert at.session_state["_modo"] == "estacion"


def test_station_controles_fuera_del_menu():
    at = AppTest.from_function(_station_script, default_timeout=60).run()
    assert not at.exception, at.exception
    assert len(at.sidebar.selectbox) == 0
    assert [s.key for s in at.main.selectbox] == ["corazon_e2__sel"]


def _two_narrators():
    from app.instruments.base import station_context
    from app.instruments.common import render_findings_narrator

    for prefix in ("e1", "e2"):
        render_findings_narrator("HRV", [("SDNN", "50 ms", "x")], ctx=station_context(prefix))


def test_narrador_se_monta_dos_veces_sin_choque():
    at = AppTest.from_function(_two_narrators, default_timeout=60)
    at.session_state[S.SESSION_KEY] = "sk-ant-prueba"
    at.run()
    assert not at.exception, at.exception
    assert sorted(b.key for b in at.button if "Explicar" in b.label) == [
        "e1__findings_narrator_HRV", "e2__findings_narrator_HRV"]


def test_main_reexporta_los_auxiliares():
    """Las pruebas viejas los importan de `app.main`: siguen ahí, y son los mismos objetos."""
    import app.main as main
    from app.instruments import common

    assert main.render_metric_explained is common.render_metric_explained
    assert main.render_findings_narrator is common.render_findings_narrator


# --------------------------------------------------------------------------------------------- Task 2: variabilidad
def _hrv_stations(save_in=None):
    """Los instrumentos de HRV montados dos veces, como dos estaciones de una misma página."""
    import streamlit as st

    from app.instruments import hrv
    from app.instruments.base import station_context

    for prefix in ("e1", "e2"):
        ctx = station_context(prefix)
        series = hrv.rr_source(ctx)
        assert series is not None
        t = hrv.tiempo(ctx, series)
        hrv.frecuencia(ctx, series)
        hrv.rsa(ctx, series)
        hrv.no_lineal(ctx, series)
        saved = hrv.guardar(ctx, series, t.values["sdnn"], t.values["mean_nn"])
        st.session_state[f"_t_{prefix}"] = dict(t.values)
        if saved.saved_snapshot_id:
            st.session_state[f"_saved_{prefix}"] = saved.saved_snapshot_id


def _short_stations(at):
    for prefix in ("e1", "e2"):          # 60 s de simulación por estación: la prueba no necesita 240
        at.session_state[f"{prefix}__hrv_duration"] = 60
    return at


def test_hrv_dos_montajes_en_una_pagina():
    at = _short_stations(AppTest.from_function(_hrv_stations, default_timeout=240)).run()
    assert not at.exception, at.exception
    assert set(at.session_state["_t_e1"]) == {"sdnn", "rmssd", "pnn50", "mean_nn"}
    keys = [b.key for b in at.button]
    assert "e1__hrv_lab_save_to_ups" in keys and "e2__hrv_lab_save_to_ups" in keys


def test_hrv_estacion_sin_menu_lateral():
    at = _short_stations(AppTest.from_function(_hrv_stations, default_timeout=240)).run()
    assert not at.exception, at.exception
    assert len(at.sidebar.slider) == 0 and len(at.sidebar.radio) == 0 and len(at.sidebar.caption) == 0
    assert {s.key for s in at.main.slider} >= {"e1__hrv_duration", "e2__hrv_duration", "e1__hrv_hr_base"}


def test_hrv_estacion_movida_no_mueve_la_otra():
    at = _short_stations(AppTest.from_function(_hrv_stations, default_timeout=240)).run()
    next(s for s in at.main.slider if s.key == "e2__hrv_amplitude").set_value(12).run()
    assert not at.exception, at.exception
    amp = {s.key: s.value for s in at.main.slider if s.key.endswith("__hrv_amplitude")}
    assert amp == {"e1__hrv_amplitude": 5, "e2__hrv_amplitude": 12}


def test_hrv_estacion_guarda_al_paciente():
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import make_session_factory
    from domain.physiology.state.models import ValueRecord

    at = _short_stations(AppTest.from_function(_hrv_stations, default_timeout=240)).run()
    next(b for b in at.button if b.key == "e2__hrv_lab_save_to_ups").click().run()
    assert not at.exception, at.exception
    snapshot_id = at.session_state["_saved_e2"]
    assert "_saved_e1" not in at.session_state
    with make_session_factory(get_shared_ups_engine())() as session:
        rows = session.query(ValueRecord).filter_by(snapshot_id=snapshot_id, descriptor="heart_rate").all()
        assert len(rows) == 1 and rows[0].source_detail.startswith("hrv_lab:sdnn_desde_serie_rr:fuente=")


# ------------------------------------------------------------------------------------------ Task 3: trazo del ECG
def _ecg_stations():
    import streamlit as st

    from app.instruments import ecg_trazo
    from app.instruments.base import station_context

    for prefix in ("e1", "e2"):
        trace = ecg_trazo.render(station_context(prefix))
        st.session_state[f"_hr_{prefix}"] = None if trace is None else trace.values.get("hr")
        if trace is not None and trace.saved_snapshot_id:
            st.session_state[f"_saved_{prefix}"] = trace.saved_snapshot_id


def _ecg_at():
    return AppTest.from_function(_ecg_stations, default_timeout=240)


def test_ecg_dos_montajes_en_una_pagina():
    at = _ecg_at().run()
    assert not at.exception, at.exception
    assert {r.key for r in at.main.radio} == {"e1__ecg_monitor_source", "e2__ecg_monitor_source"}
    assert at.session_state["_hr_e1"] is not None and at.session_state["_hr_e2"] is not None   # la demo mide su FC


def test_ecg_estacion_sin_menu_lateral_ni_placa_en_vivo():
    at = _ecg_at().run()
    assert not at.exception, at.exception
    sb = at.sidebar
    assert not (sb.radio or sb.slider or sb.selectbox or sb.button or sb.caption or sb.info or sb.warning)
    for radio in at.main.radio:
        assert "Hardware ESP32 en vivo" not in radio.options
        assert "Demo (sintético)" in radio.options and "Paciente activo (simulación a su FC)" in radio.options


def test_ecg_estacion_movida_no_mueve_la_otra():
    at = _ecg_at().run()
    next(s for s in at.main.slider if s.key == "e2__ecg_demo_hr").set_value(130).run()
    assert not at.exception, at.exception
    assert round(at.session_state["_hr_e2"]) == 130 and round(at.session_state["_hr_e1"]) == 72


def _value_rows():
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import make_session_factory
    from domain.physiology.state.models import ValueRecord

    with make_session_factory(get_shared_ups_engine())() as session:
        return session.query(ValueRecord).count()


def test_ecg_estacion_no_guarda_demo():
    """La compuerta de siempre en una estación: la demo no ofrece guardar (y no escribe nada); un caso clínico sí, y
    solo escribe la estación cuyo botón se pulsó."""
    at = _ecg_at().run()
    assert not at.exception, at.exception
    assert not [b for b in at.button if b.key and b.key.endswith("ecg_lab_save_to_ups")]
    assert any("Fuente demo (sintética) -- nunca escribe HR al gemelo" in i.value for i in at.info)

    before = _value_rows()
    at.radio(key="e1__ecg_monitor_source").set_value("Caso clínico (61 disponibles)").run()
    assert not at.exception, at.exception
    assert _value_rows() == before
    at.button(key="e1__ecg_lab_save_to_ups").click().run()
    assert not at.exception, at.exception
    assert "_saved_e2" not in at.session_state
    if "_saved_e1" in at.session_state:          # la compuerta clínica puede declinar el caso; si escribe, es de e1
        assert _value_rows() > before
    else:
        assert any("Escritura declinada" in w.value for w in at.warning)


def test_monitoreo_avisa_una_sola_vez_si_faltan_los_modulos_src():
    """Revisión final de la T2: la página volvía a importar los módulos de `src` tras el instrumento y, sin ellos, el
    aviso salía dos veces (antes de la T2, una)."""
    def _script():
        import streamlit as st

        import app.instruments.ecg_trazo as E
        import app.main as m

        def fake():
            st.warning("SRC-FALTA")
            return {}, False

        original = E.safe_import_src_modules       # los módulos se comparten entre pruebas: se restaura siempre
        E.safe_import_src_modules = m.safe_import_src_modules = fake
        try:
            m.render_ecg_monitor_page()
        finally:
            E.safe_import_src_modules = m.safe_import_src_modules = original

    at = AppTest.from_function(_script, default_timeout=240).run()
    assert not at.exception, at.exception
    assert [w.value for w in at.warning].count("SRC-FALTA") == 1
