"""Pasaporte de evidencia (2026-11-17): muestra exactamente lo que dice el registro, nada inventado.

- Cada cita del registro existe, literal, en el archivo de su ubicación (Art. I: el registro no redacta).
- El tipo de dato sale de la procedencia por la tabla explícita; las 7 procedencias del UPS tienen fila.
- Un apartado sin cita dice «no documentado»; un campo fuera del registro no dibuja nada.
- Todo resultado de Calculadoras y cada valor del banner tienen su entrada.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.utils import evidence_passport as P
from app.utils import evidence_registry as R
from domain.physiology.state.schema import Provenance

ROOT = Path(__file__).resolve().parents[1]


def _norm(text: str) -> str:
    lines = [re.sub(r"^#+\s?", "", line.strip()) for line in text.splitlines()]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _citas(ev: R.Evidencia):
    for name in ("procedencia_cita", "regla", "supuestos", "no_modelado"):
        cita = getattr(ev, name)
        if cita is not None:
            yield name, cita
    if ev.fuente is not None and ev.fuente.cita is not None:
        yield "fuente", ev.fuente.cita


def test_the_registry_covers_the_banner_and_the_calculators():
    # Las tarjetas del gemelo viven en twin_shell/ (otra dueña): su registro y su línea llegan en la siguiente tanda.
    assert {"banner", "calculadoras"} <= {e.superficie for e in R.REGISTRY.values()}


def test_every_provenance_has_a_row_and_the_types_are_the_five():
    assert set(P.PROVENANCE_TYPE) == set(Provenance)
    assert set(P.PROVENANCE_TYPE.values()) <= set(P.DATA_TYPES) and len(P.DATA_TYPES) == 5
    assert set(P.DATA_TYPE_MEANING) == set(P.DATA_TYPES)
    assert P.data_type(None) == P.data_type("variable") == "desconocido"
    assert P.data_type("SIMULACION") == P.data_type(Provenance.SIMULACION) == "simulado"
    assert P.data_type("sensor_real") == "medido"


@pytest.mark.parametrize("campo", sorted(R.REGISTRY))
def test_registry_entry_is_well_formed(campo):
    ev = R.REGISTRY[campo]
    assert ev.superficie in R.SURFACES and campo.startswith(ev.superficie + ".")
    assert ev.etiqueta.strip()
    assert ev.procedencia in (None, P.VARIABLE) or ev.procedencia in Provenance.__members__


@pytest.mark.parametrize("campo", sorted(R.REGISTRY))
def test_every_quote_exists_literally_in_its_file(campo):
    for name, cita in _citas(R.REGISTRY[campo]):
        path = ROOT / cita.archivo
        assert path.is_file(), (campo, name, cita.ubicacion)
        source = path.read_text(encoding="utf-8")
        line = int(cita.ubicacion.rsplit(":", 1)[1])
        assert 1 <= line <= len(source.splitlines()), (campo, name, cita.ubicacion)
        assert _norm(cita.texto) in _norm(source), (campo, name, cita.texto[:80])


def test_sources_point_to_the_bibliography():
    from app.supermodules.bibliography import SIGNED_KEYS, _uniform, repo_references

    listed = {r.text for r in repo_references()}
    for campo, ev in R.REGISTRY.items():
        if ev.fuente is None:
            continue
        if ev.fuente.clave:
            assert ev.fuente.clave in SIGNED_KEYS, campo
        if ev.fuente.constante:
            module_name, _, attr = ev.fuente.constante.rpartition(".")
            import importlib

            citation = getattr(importlib.import_module(module_name), attr)
            assert _uniform(citation)[0] in listed, campo


@pytest.mark.parametrize("campo", sorted(R.REGISTRY))
def test_the_passport_shows_exactly_the_registry(campo):
    ev = R.REGISTRY[campo]
    view = P.passport_view(campo, "72 lpm")
    assert (view.etiqueta, view.valor) == (ev.etiqueta, "72 lpm")
    assert (view.produce, view.origen) == (ev.produce, ev.origen)
    assert (view.regla, view.supuestos, view.no_modelado, view.procedencia_cita) == (
        ev.regla, ev.supuestos, ev.no_modelado, ev.procedencia_cita)
    expected_type = P.data_type(None if ev.procedencia == P.VARIABLE else ev.procedencia)
    assert view.tipo == expected_type and view.tipo in P.DATA_TYPES


def test_runtime_provenance_wins_over_the_registry():
    campo = "banner.fc"
    assert P.passport_view(campo, "72 lpm", Provenance.SENSOR_REAL).tipo == "medido"
    assert P.passport_view(campo, "72 lpm", Provenance.SIMULACION).tipo == "simulado"
    assert P.passport_view(campo, None).valor == P.NO_VALUE


def test_unknown_field_draws_nothing():
    assert P.passport_view("no.existe", 1) is None


def _body_script(campo: str):
    from app.utils.evidence_passport import passport_view, render_passport_body

    render_passport_body(passport_view(campo, "72 lpm"))


@pytest.mark.parametrize("campo", sorted(R.REGISTRY)[:6] + ["calculadoras.bmi", "banner.fc"])
def test_the_rendered_passport_has_the_seven_sections_and_nothing_invented(campo):
    ev = R.REGISTRY[campo]
    at = AppTest.from_function(_body_script, args=(campo,), default_timeout=30)
    at.run()
    assert not at.exception
    texts = [m.value for m in at.markdown]
    titles = [t[2:-2] for t in texts if t.startswith("**") and t.endswith("**")]
    assert titles == list(P.SECTIONS)
    joined = "\n".join(texts)
    for cita in (ev.regla, ev.supuestos, ev.no_modelado):
        if cita is not None:
            assert html.escape(cita.texto) in joined
    missing = sum(c is None for c in (ev.regla, ev.supuestos, ev.no_modelado))
    missing += 0 if (ev.produce or ev.origen) else 1
    view = P.passport_view(campo, "72 lpm")
    missing += 1 if view.fuente is None or (view.fuente.referencia is None and view.fuente.cita is None) else 0
    assert texts.count(P.NOT_DOCUMENTED) == missing


def test_every_calculator_card_and_banner_value_has_an_entry():
    src = (ROOT / "app/supermodules/calculators/pages.py").read_text(encoding="utf-8")
    ids = set(re.findall(r'_card\(\s*"([a-z0-9_]+)"', src))
    from clinical import calculators as calc

    ids |= {f"qtc_{name}" for name in calc.qtc_all(400.0, 60.0)}
    ids |= {f"news2_paciente_{key}" for key in ("hr", "rr", "spo2")}
    missing = sorted(i for i in ids if f"calculadoras.{i}" not in R.REGISTRY)
    assert not missing, missing
    from app.utils.patient_banner import PASSPORT_FIELDS

    assert set(PASSPORT_FIELDS.values()) <= set(R.REGISTRY)


def test_calculators_page_places_the_passports():
    at = AppTest.from_file(str(ROOT / "app/main.py"), default_timeout=240)
    at.session_state["biocore_start_page"] = "calculadoras"
    at.run()
    assert not at.exception
    rule_titles = [m.value for m in at.markdown if m.value == f"**{P.SECTION_RULE}**"]
    assert len(rule_titles) >= 10
