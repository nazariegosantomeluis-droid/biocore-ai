"""T6 de la ruta integrada (2026-11-18): las reglas firmadas disparan en el flujo normal de la Ruta y se declaran.

Diseño firmado, T6: «la estación de cierre de la Unidad Cerebro llama al compositor justo después de guardar el EEG,
si hay una FC del paciente dentro de la ventana. La regla dispara en el flujo normal y la estación lo declara: qué
regla, con qué cita, con qué confianza». Prueba de cierre: «La regla BAR dispara en la ruta; reglas nuevas — coupling/,
estación de cierre de Cerebro — La regla dispara en el flujo normal y se declara». La segunda regla firmada
(`HIPOXIA_TAQUICARDIA`, ficha 1) se evalúa igual en la Unidad Respiración.

Sin botón «Componer»: cada guardado de la unidad (el EEG o la SpO₂ en «Mide», la FC en el cierre) evalúa la regla de
la unidad con `evaluate_rule_for_patient`, con el escenario de la unidad (los bloqueos por regla se aplican).
"""

import pytest

from tests.test_ruta_unidades_t4 import _button, _composed, _go, _save_eeg, _start, _texts

HR_SAVE = "ruta_{unit}_fc__hrv_lab_save_to_ups"


def _measure_hr(at, unit):
    _button(at, HR_SAVE.format(unit=unit)).click().run()
    assert at.exception == [], at.exception
    return at


def _hr_of(at, name):
    d = _composed(at).state.cardiovascular.get(name)
    return None if d is None else d


# ── Unidad Cerebro: AROUSAL_TAQUICARDIA_BAR ────────────────────────────────────────────────────────────────────────
def test_cerebro_la_regla_dispara_al_medir_la_fc_despues_del_eeg_y_se_declara():
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    _measure_hr(at, "cerebro")
    coupled = _hr_of(at, "heart_rate_acoplado")
    assert coupled is not None and coupled.provenance.name == "DERIVADO_ACOPLAMIENTO"   # «Beta (activo)»: BAR > 1.8
    text = _texts(at)
    assert "AROUSAL_TAQUICARDIA_BAR se aplicó" in text and "Guyton" in text and "0.70" in text
    assert "basal 0.8–1.2" in text and "no crece con el BAR" in text                     # rango de la fuente (T4.1)
    assert _button(at, "ruta_cerebro_compose") is None                                     # sin botón: flujo normal


def test_cerebro_la_regla_dispara_al_guardar_el_eeg_si_ya_hay_una_fc_medida():
    """El orden del diseño: «llama al compositor justo después de guardar el EEG, si hay una FC dentro de la
    ventana»."""
    at = _go(_start("cerebro"), "cerebro", "cierre")
    _measure_hr(at, "cerebro")
    assert _hr_of(at, "heart_rate_acoplado") is None                                      # todavía no hay EEG
    _save_eeg(at)
    assert _hr_of(at, "heart_rate_acoplado") is not None
    _go(at, "cerebro", "cierre")
    assert "AROUSAL_TAQUICARDIA_BAR se aplicó" in _texts(at)


def test_cerebro_con_la_fc_del_escenario_dice_que_es_una_proyeccion():
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    assert "proyección de un escenario" in _texts(at) and _hr_of(at, "heart_rate_acoplado") is None


def test_cerebro_no_reacopla_al_volver_a_dibujar():
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    _measure_hr(at, "cerebro")
    at.run()
    _go(at, "cerebro", "mide")
    _go(at, "cerebro", "cierre")
    from sqlalchemy import func, select

    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import make_session_factory
    from domain.physiology.state.models import SnapshotRecord, ValueRecord

    with make_session_factory(get_shared_ups_engine())() as s:
        n = s.execute(select(func.count()).select_from(ValueRecord)
                      .join(SnapshotRecord, ValueRecord.snapshot_id == SnapshotRecord.id)
                      .where(SnapshotRecord.patient_id == at.session_state["twin_shell_ups_patient_id"],
                             ValueRecord.descriptor == "heart_rate_acoplado")).scalar_one()
    assert n == 1


def test_cerebro_en_estres_no_evalua_ni_ofrece_medir():
    at = _go(_save_eeg(_start("cerebro", "stress")), "cerebro", "cierre")
    assert "no se evalúa en el escenario Estrés" in _texts(at)
    assert _button(at, HR_SAVE.format(unit="cerebro")) is None


# ── Unidad Respiración: HIPOXIA_TAQUICARDIA ────────────────────────────────────────────────────────────────────────
def _save_spo2(at, spo2):
    _go(at, "respiracion", "mide")
    at.number_input(key="ruta_respiracion_mide__resp_spo2_basal").set_value(spo2).run()
    _button(at, "ruta_respiracion_mide__respiratory_lab_save_to_ups").click().run()
    assert at.exception == [], at.exception
    return at


def test_respiracion_la_regla_de_hipoxia_dispara_y_se_declara():
    at = _go(_save_spo2(_start("respiracion"), 88), "respiracion", "cierre")
    _measure_hr(at, "respiracion")
    hr, coupled = _hr_of(at, "heart_rate"), _hr_of(at, "heart_rate_acoplado")
    assert coupled is not None and coupled.value == pytest.approx(hr.value + 13.0)
    text = _texts(at)
    assert "HIPOXIA_TAQUICARDIA se aplicó" in text and "Halliwill" in text and "0.70" in text
    assert "evalúa todavía las reglas" not in text


def test_respiracion_con_spo2_normal_la_regla_se_evalua_y_no_se_aplica():
    at = _go(_save_spo2(_start("respiracion"), 97), "respiracion", "cierre")
    _measure_hr(at, "respiracion")
    assert _hr_of(at, "heart_rate_acoplado") is None
    assert "HIPOXIA_TAQUICARDIA se evaluó y no se aplicó" in _texts(at)


@pytest.mark.parametrize("scenario,label", [("hypoxia", "Hipoxia"), ("copd", "EPOC")])
def test_respiracion_en_un_escenario_bloqueado_no_evalua_ni_ofrece_medir(scenario, label):
    at = _go(_start("respiracion", scenario), "respiracion", "cierre")
    assert f"no se evalúa en el escenario {label}" in _texts(at)
    assert _button(at, HR_SAVE.format(unit="respiracion")) is None


def test_respiracion_ya_no_lista_la_regla_como_pendiente():
    from app.supermodules.ruta import respiracion

    assert not any("hipoxia" in title.lower() for title, _why in respiracion.UNIT.pending)


def test_empezar_de_nuevo_borra_el_resultado_de_la_regla():
    from app.supermodules.ruta import coupling_station as CS

    at = _go(_save_spo2(_start("respiracion"), 88), "respiracion", "cierre")
    _measure_hr(at, "respiracion")
    assert CS.result_key("ruta_respiracion_") in at.session_state
    _go(at, "respiracion", "paciente")
    _button(at, "ruta_respiracion_start").click().run()          # «Empezar de nuevo con este escenario»
    assert at.exception == [], at.exception
    assert CS.result_key("ruta_respiracion_") not in at.session_state


def test_la_fc_proyectada_no_se_rotula_como_medicion():
    at = _go(_start("cerebro"), "cerebro", "cierre")
    text = _texts(at)
    assert "Última medición: FC" not in text and "proyección del escenario, no cuenta como medición" in text


def test_el_motivo_va_en_espanol_y_sin_tiempo_contra_una_proyeccion():
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    text = _texts(at)
    assert "heart_rate" not in text and "spo2" not in text and "proyección" in text
    assert "Tiempo entre las dos mediciones" not in text            # una proyección no es un momento



def test_sin_rotulos_internos_ni_horizonte_crudo():
    """Revisión final de la T6: «T6:» y «DERIVADO_ACOPLAMIENTO» se veían en la estación; el horizonte iba crudo."""
    at = _go(_save_eeg(_start("cerebro")), "cerebro", "cierre")
    text = _texts(at)
    assert "T6" not in text and "DERIVADO_ACOPLAMIENTO" not in text
    assert "horizonte 7d" not in text and "horizonte 7 días" in text


def test_un_resultado_viejo_no_se_muestra_junto_a_mediciones_nuevas():
    """Una FC guardada fuera de la unidad (p. ej. en Variabilidad cardiaca) no reevalúa: el cierre no muestra el
    resultado anterior junto a la medición nueva."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from app.utils.patient_session import get_shared_ups_engine
    from domain.physiology.state import Provenance, from_digital_twin_organism, make_session_factory, save_state

    at = _go(_save_spo2(_start("respiracion"), 88), "respiracion", "cierre")
    _measure_hr(at, "respiracion")
    assert "se aplicó" in _texts(at)
    o = DigitalTwinOrganism()
    o.update_from_sensors({"ecg": {"heart_rate": 95.0}})
    state = from_digital_twin_organism(o, at.session_state["twin_shell_ups_patient_id"], Provenance.SIMULACION, 0.85,
                                       source_detail="hrv_lab:fuera de la unidad")
    with make_session_factory(get_shared_ups_engine())() as s:
        save_state(s, state)
    at.run()
    text = _texts(at)
    assert "se aplicó" not in text and "Hay mediciones nuevas" in text


def test_dos_reglas_a_la_vez_lo_dice_la_estacion():
    from app.supermodules.ruta import coupling_station as CS
    from streamlit.testing.v1 import AppTest

    def script():
        import streamlit as st
        from app.supermodules.ruta import coupling_station as CS
        from domain.physiology.coupling import HIPOXIA_TAQUICARDIA

        st.session_state[CS.result_key("p_")] = {
            "rule_id": "HIPOXIA_TAQUICARDIA", "available": True, "reason": None, "already": False, "wrote": False,
            "gap_s": 0.0, "condition": "SpO₂ 88 % · Simulación", "base": "FC 70 lpm · Simulación", "observed": 88.0,
            "coupled": None, "combined_with": ["AROUSAL_TAQUICARDIA_BAR"], "inputs": None}
        CS.render_result("p_", HIPOXIA_TAQUICARDIA)

    at = AppTest.from_function(script)
    at.run()
    text = " ".join(i.value for i in at.info)
    assert "AROUSAL_TAQUICARDIA_BAR" in text and "no se escribe ninguna" in text and "no cumple" not in text
