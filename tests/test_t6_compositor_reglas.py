"""T6 de la ruta integrada (2026-11-18): el compositor generalizado a los pares de cada regla firmada.

Diseño: «Generalizar el compositor a pares de descriptores definidos por las reglas firmadas, en vez de solo bar +
heart_rate, cuando exista la segunda regla». Decisión 1 firmada: la ventana fisiológica es estricta y solo para
acoplamientos; cada regla trae la suya (BAR: los 120 s de la FC; hipoxia: 120 s, ficha 1).

`evaluate_rule_for_patient(session, patient_id, rule, scenario=...)`:
- toma la última condición y la última FC MEDIDAS: nunca la copia de una composición anterior (lección de la T4) ni la
  proyección de un escenario (un horizonte no es un momento);
- si están en el mismo guardado, evalúa ese guardado; si no, compone uno nuevo (la más vieja como arrastre, con su
  edad), solo si las separa como mucho la ventana de la regla;
- respeta los escenarios bloqueados (los globales y los de la regla) sin escribir nada;
- no vuelve a acoplar un guardado ya evaluado.
"""

import dataclasses
from datetime import timedelta

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.coupling import (
    AROUSAL_TAQUICARDIA_BAR,
    HIPOXIA_TAQUICARDIA,
    evaluate_rule_for_patient,
    latest_measured,
)
from domain.physiology.state import (
    Provenance,
    create_patient,
    from_digital_twin_organism,
    get_state_by_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def sf(tmp_path):
    engine = make_engine(tmp_path / "t6.db")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture
def pid(sf):
    with sf() as s:
        return create_patient(s, display_name="t6")


# T6.1: la regla BAR exige un EEG de vigilia (las cuatro bandas; theta y delta bajas).
_SLOW = {"theta_power": 0.5, "delta_power": 0.5}


def _save(sf, pid, sensors, detail="prueba:medida", age_s=0.0):
    o = DigitalTwinOrganism()
    o.update_from_sensors(sensors)
    state = from_digital_twin_organism(o, pid, Provenance.SIMULACION, 0.85, source_detail=detail)
    if age_s:
        state = dataclasses.replace(state, timestamp=state.timestamp - timedelta(seconds=age_s))
    with sf() as s:
        return save_state(s, state)


def test_cada_regla_firmada_declara_su_ventana():
    assert AROUSAL_TAQUICARDIA_BAR.window_s == 120.0 and HIPOXIA_TAQUICARDIA.window_s == 120.0


def test_hipoxia_en_el_mismo_guardado_se_evalua_sin_escribir_otro(sf, pid):
    snap = _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario="healthy")
        assert r.available and not r.wrote_snapshot and r.snapshot_id == snap
        assert r.coupled is not None and r.coupled.coupled_value == pytest.approx(83.0)
        assert get_state_by_snapshot_id(s, snap).cardiovascular.get("heart_rate_acoplado").value == pytest.approx(83.0)


def test_un_guardado_ya_evaluado_no_se_vuelve_a_acoplar(sf, pid):
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0}})
    with sf() as s:
        evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
        r = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
    assert r.available and r.already_evaluated and r.coupled is None


def test_bar_y_fc_en_guardados_distintos_se_componen_con_la_mas_vieja_como_arrastre(sf, pid):
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}}, detail="hrv_lab:prueba", age_s=30)
    _save(sf, pid, {"eeg": {"alpha_power": 10.0, "beta_power": 30.0, **_SLOW}}, detail="eeg_neuro_lab:prueba")
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario="healthy")
        assert r.available and r.wrote_snapshot and r.gap_s == pytest.approx(30, abs=2)
        state = get_state_by_snapshot_id(s, r.snapshot_id)
    hr = state.cardiovascular.get("heart_rate")
    assert hr.provenance == Provenance.ARRASTRE_TEMPORAL and "edad" in hr.source_detail
    assert state.neurological.get("bar").provenance == Provenance.SIMULACION
    assert state.cardiovascular.get("heart_rate_acoplado").value == pytest.approx(85.0)


def test_fuera_de_la_ventana_no_compone_y_dice_cual_es_mas_viejo(sf, pid):
    _save(sf, pid, {"eeg": {"alpha_power": 10.0, "beta_power": 30.0, **_SLOW}}, age_s=300)
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario=None)
    assert not r.available and "bar" in r.reason and "120" in r.reason and r.snapshot_id is None


def test_la_fc_proyectada_de_un_escenario_no_cuenta_como_medicion(sf, pid):
    _save(sf, pid, {"ecg": {"heart_rate": 72.0}, "respiratory": {"spo2": 88.0}}, detail="escenario_rico:healthy:modo:nuevo:horizonte:7d")
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
    assert not r.available and "proyección" in r.reason


def test_las_copias_de_una_composicion_no_se_vuelven_a_componer(sf, pid):
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}}, age_s=10)
    _save(sf, pid, {"eeg": {"alpha_power": 10.0, "beta_power": 30.0, **_SLOW}})
    with sf() as s:
        first = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario=None)
        measured = latest_measured(s, pid, "cardiovascular", "heart_rate")
        assert measured.snapshot_id != first.snapshot_id                 # la copia no es una medición
        second = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario=None)
    assert second.available and second.already_evaluated and second.coupled is None


@pytest.mark.parametrize("rule,scenario", [(HIPOXIA_TAQUICARDIA, "hypoxia"), (HIPOXIA_TAQUICARDIA, "stress"),
                                           (AROUSAL_TAQUICARDIA_BAR, "anxiety")])
def test_un_escenario_bloqueado_no_escribe_nada(sf, pid, rule, scenario):
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 85.0},
                    "eeg": {"alpha_power": 10.0, "beta_power": 30.0, **_SLOW}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, rule, scenario=scenario)
        assert not r.available and scenario in r.reason
        assert latest_measured(s, pid, "cardiovascular", "heart_rate_acoplado") is None


def test_sin_condicion_o_sin_fc_dice_que_falta(sf, pid):
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
    assert not r.available and "spo2" in r.reason


def test_una_composicion_sin_acoplar_tampoco_se_repite(sf, pid):
    """BAR bajo (la regla no se cumple): la composición se escribe una vez; evaluar de nuevo no escribe otra."""
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}}, age_s=10)
    _save(sf, pid, {"eeg": {"alpha_power": 30.0, "beta_power": 10.0, **_SLOW}})
    with sf() as s:
        first = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario=None)
        second = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario=None)
    assert first.wrote_snapshot and first.coupled is None
    assert second.already_evaluated and not second.wrote_snapshot


def test_el_paciente_compuesto_muestra_la_fc_acoplada_por_la_regla_de_hipoxia(sf, pid):
    """T6: con dos reglas, las entradas de la FC acoplada salen de SU regla (`acoplamiento:<regla>`), no de una tabla
    fija con el BAR: si no, la FC acoplada por la hipoxia nunca se veía en el paciente compuesto."""
    from domain.physiology.state import get_composed_patient

    _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0}})
    with sf() as s:
        evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario="healthy")
        coupled = get_composed_patient(s, pid).state.cardiovascular.get("heart_rate_acoplado")
    assert coupled is not None and coupled.value == pytest.approx(83.0)


def test_la_fc_acoplada_no_viaja_si_su_condicion_ya_no_es_la_ultima(sf, pid):
    from domain.physiology.state import get_composed_patient

    _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0}})
    with sf() as s:
        evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
    _save(sf, pid, {"respiratory": {"spo2": 97.0}})                    # la SpO₂ cambió: la FC acoplada ya no vale
    with sf() as s:
        assert get_composed_patient(s, pid).state.cardiovascular.get("heart_rate_acoplado") is None


def test_la_fc_acoplada_de_una_regla_que_no_esta_en_el_catalogo_no_viaja(sf, pid):
    from domain.physiology.state import PhysiologicalDescriptor, get_composed_patient

    o = DigitalTwinOrganism()
    o.update_from_sensors({"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0}})
    state = from_digital_twin_organism(o, pid, Provenance.SIMULACION, 0.85, source_detail="prueba")
    state.cardiovascular.descriptors["heart_rate_acoplado"] = PhysiologicalDescriptor(
        name="heart_rate_acoplado", value=99.0, unit="bpm", provenance=Provenance.DERIVADO_ACOPLAMIENTO,
        confidence=0.7, source_detail="acoplamiento:REGLA_RETIRADA | x")
    with sf() as s:
        save_state(s, state)
        assert get_composed_patient(s, pid).state.cardiovascular.get("heart_rate_acoplado") is None


def test_en_el_gemelo_una_spo2_movida_quita_la_fc_acoplada_por_la_hipoxia(sf, pid):
    """El gemelo superpone el estado de los sliders al paciente: un derivado del paciente se quita si el estado actual
    trae una de sus entradas. Las de la FC acoplada por la hipoxia son la SpO₂ y la FC, no el BAR."""
    from app.utils.physiological_state import overlay_current_on_composed
    from domain.physiology.state import get_composed_patient

    _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0}})
    with sf() as s:
        evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
        composed = get_composed_patient(s, pid)
    o = DigitalTwinOrganism()
    o.update_from_sensors({"respiratory": {"spo2": 97.0}})
    now = from_digital_twin_organism(o, pid, Provenance.SIMULACION, 0.85, source_detail="gemelo")
    state, _origins = overlay_current_on_composed(now, composed)
    assert state.cardiovascular.get("heart_rate_acoplado") is None


# ── Revisión final de la T6 ─────────────────────────────────────────────────────────────────────────────────────────
def _carried_events(sf, pid):
    from app.utils.physiological_state import with_carried_events
    from domain.physiology.state import get_composed_patient

    with sf() as s:
        return with_carried_events(s, get_composed_patient(s, pid))


def test_una_composicion_no_esconde_los_puntos_news2_ni_el_aviso_de_spo2(sf, pid):
    """Hallazgo crítico: el snapshot de la regla (copias) pasaba a ser el último; los puntos NEWS2 y el evento
    SPO2_NEWS2_3_POINTS se perdían justo cuando la regla de hipoxia declara la hipoxia. Una copia no es información
    nueva: el paciente compuesto lee los originales."""
    spo2_snap = _save(sf, pid, {"respiratory": {"spo2": 88.0, "respiratory_rate": 16.0}}, age_s=30)
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario="healthy")
    assert r.wrote_snapshot and r.coupled is not None
    composed = _carried_events(sf, pid)
    assert composed.state.respiratory.get("news2_spo2_scale1_points").value == 3
    assert composed.state.cardiovascular.get("news2_pulse_points") is not None
    assert composed.origins[("respiratory", "spo2")].snapshot_id == spo2_snap     # la SpO₂ original, con su edad
    assert any(e.event_type.name == "SPO2_NEWS2_3_POINTS" for e in composed.state.events)
    assert composed.state.cardiovascular.get("heart_rate_acoplado").value == pytest.approx(83.0)


def test_dos_reglas_que_cambian_la_fc_en_el_mismo_guardado_no_escriben_nada(sf, pid):
    """Política firmada de no combinar: evaluar una regla sola la saltaba; y la otra decía «ya evaluaste»."""
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "respiratory": {"spo2": 88.0},
                    "eeg": {"alpha_power": 10.0, "beta_power": 30.0, **_SLOW}})
    with sf() as s:
        bar = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario="healthy")
        hyp = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario="healthy")
        assert latest_measured(s, pid, "cardiovascular", "heart_rate_acoplado") is None
    assert bar.coupled is None and bar.combined_with == ("HIPOXIA_TAQUICARDIA",)
    assert not hyp.already_evaluated and hyp.combined_with == ("AROUSAL_TAQUICARDIA_BAR",)


def test_un_eeg_nuevo_sin_bar_no_usa_el_bar_anterior(sf, pid):
    _save(sf, pid, {"eeg": {"alpha_power": 10.0, "beta_power": 30.0, **_SLOW}}, age_s=50)
    _save(sf, pid, {"eeg": {"alpha_power": 0.0, "beta_power": 30.0, **_SLOW}}, age_s=20)
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario=None)
    assert not r.available and "no lo trae" in r.reason


def test_un_arrastre_del_gemelo_no_esconde_los_valores_frescos_de_su_guardado(sf, pid):
    from domain.physiology.state import PhysiologicalDescriptor

    _save(sf, pid, {"respiratory": {"spo2": 88.0}}, age_s=20)
    o = DigitalTwinOrganism()
    o.update_from_sensors({"ecg": {"heart_rate": 70.0}})
    state = from_digital_twin_organism(o, pid, Provenance.SIMULACION, 0.85, source_detail="gemelo")
    state.respiratory.descriptors["spo2"] = PhysiologicalDescriptor(
        name="spo2", value=88.0, unit="%", provenance=Provenance.ARRASTRE_TEMPORAL, confidence=0.85,
        source_detail="arrastre del organismo")
    with sf() as s:
        twin = save_state(s, state)
        assert latest_measured(s, pid, "cardiovascular", "heart_rate").snapshot_id == twin
        spo2 = latest_measured(s, pid, "respiratory", "spo2")
    assert spo2.snapshot_id != twin and spo2.descriptor.value == pytest.approx(88.0)


def test_una_regla_cuyo_nombre_empieza_igual_no_cuenta_como_ya_compuesta(sf, pid):
    from domain.physiology.state import PhysiologicalDescriptor, UnifiedPhysiologicalState, DomainState
    from datetime import datetime, timezone

    spo2 = _save(sf, pid, {"respiratory": {"spo2": 88.0}}, age_s=10)
    hr = _save(sf, pid, {"ecg": {"heart_rate": 70.0}})
    fake = PhysiologicalDescriptor(name="heart_rate", value=70.0, unit="bpm", provenance=Provenance.ARRASTRE_TEMPORAL,
                                   confidence=0.85,
                                   source_detail=f"heart_rate copiado del snapshot {hr} para la regla "
                                                 f"HIPOXIA_TAQUICARDIA_2 (spo2 del snapshot {spo2})")
    other = UnifiedPhysiologicalState(
        patient_id=pid, timestamp=datetime.now(timezone.utc), events=[],
        cardiovascular=DomainState(domain="cardiovascular", descriptors={"heart_rate": fake}),
        respiratory=DomainState(domain="respiratory", descriptors={"spo2": PhysiologicalDescriptor(
            name="spo2", value=88.0, unit="%", provenance=Provenance.SIMULACION, confidence=0.85,
            source_detail=f"spo2 copiado del snapshot {spo2} para la regla HIPOXIA_TAQUICARDIA_2")}),
        neurological=DomainState(domain="neurological", descriptors={}),
        muscular=DomainState(domain="muscular", descriptors={}))
    with sf() as s:
        save_state(s, other)
        r = evaluate_rule_for_patient(s, pid, HIPOXIA_TAQUICARDIA, scenario=None)
    assert r.wrote_snapshot and not r.already_evaluated
