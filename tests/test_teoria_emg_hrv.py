"""Teoría citada 2 (2026-11-17): EMG (A1–A9) y HRV (B1–B9) firmados en `docs/contenido/teoria_citada_2.md`, y las
etiquetas que contradecían lo firmado.

PARTE A — cada tema está en Aprender y en la «Teoría» de su laboratorio; nada de lo listado como «sin fuente
verificada» se escribe; [TF1996] no sostiene ninguna afirmación.
PARTE B — razón LF/HF siempre «(interpretación discutida)» con [B2013] y nunca como balance/estrés; EMG sin deducir
fuerza de la amplitud; HRV sin postura/fármacos/ejercicio ni cifras de normalidad; escenarios STEMI nombrados por lo
que se ve en el trazado.
(El recorrido de TODAS las páginas y fuentes con la guardia de LF/HF está en `test_fase1_t2_pulido.py`.)
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.supermodules import learn_theory as LT

MAIN = str(Path("app/main.py").resolve())
DOC2 = Path("docs/contenido/teoria_citada_2.md").read_text(encoding="utf-8")
SECTIONS = ("Cómo se calcula", "Simular", "Teoría", "Narración con IA (opcional)")


def _open(url, **state):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = url
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert at.exception == [], (url, at.exception)
    return at


def _texts(at):
    from test_fase1_t2_pulido import visible_texts

    return visible_texts(at)


# ── PARTE A ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_second_signed_document_is_fully_signed_and_every_topic_is_integrated():
    assert "FIRMADO por Luis Nazariego Santome el 17 de noviembre de 2026" in DOC2 and "☐" not in DOC2
    titles = re.findall(r"^## ([AB]\d)\. (.+)$", DOC2, re.M)
    assert [code for code, _ in titles] == [f"A{i}" for i in range(1, 10)] + [f"B{i}" for i in range(1, 10)]
    assert len(LT.EMG_TOPICS) == 9 and len(LT.HRV_TOPICS) == 9
    refs = LT.LEARN_TOPICS["referencias"]
    assert all(t in refs for t in LT.EMG_TOPICS + LT.HRV_TOPICS)
    for t in LT.EMG_TOPICS + LT.HRV_TOPICS:
        assert LT.ORIGINS[t.title] == (LT.SIGNED_DOC_2,)                  # la prueba literal lo busca en este documento


def test_what_the_document_lists_as_unsourced_is_never_written():
    text = " ".join(x for t in LT.EMG_TOPICS + LT.HRV_TOPICS
                    for x in (t.idea, t.mechanism, t.detail if isinstance(t.detail, str) else "") if x).lower()
    for unsourced in ("tronco", "ecg", "postura", "fármaco", "ejercicio", "lesión", "diagnóstic"):
        assert unsourced not in text, unsourced
    assert not re.search(r"\d+\s*mm", text)                             # dimensiones SENIAM excluidas
    assert "[TF1996]" not in text and all("[TF1996]" not in (t.source or "") for t in LT.EMG_TOPICS + LT.HRV_TOPICS)


def test_tf1996_carries_its_note_and_the_seven_new_references_are_listed():
    from app.supermodules.bibliography import SIGNED

    by_key = {r.key: r for r in SIGNED}
    for key in ("DL1997", "DL2010", "V2018", "H2000", "SG2017", "B2013", "TF1996"):
        assert key in by_key, key
    assert "no se le atribuye ninguna afirmación directamente" in by_key["TF1996"].note
    at = _open("bibliografia")
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "**[TF1996]**" in text and "no se le atribuye ninguna afirmación directamente" in text


@pytest.mark.parametrize("url, topics", [("emg", "EMG_TOPICS"), ("hrv", "HRV_TOPICS")])
def test_each_lab_has_its_signed_theory_linked_to_the_bibliography(url, topics):
    at = _open(url)
    titles = [m.value[5:] for m in at.markdown if m.value.startswith("#### ")]
    for t in getattr(LT, topics):
        assert t.title in titles, (url, t.title)
    theory = next(e for e in at.expander if e.label == "Teoría")
    assert not theory.proto.expanded
    assert any("referencias" in p.proto.page for p in at.get("page_link"))


def test_learn_references_page_groups_emg_and_hrv():
    at = _open("referencias")
    md = [m.value for m in at.main.markdown]
    assert any("EMG de superficie" in m for m in md) and any("Variabilidad de la frecuencia cardiaca (HRV)" in m for m in md)


def test_value_explanations_use_only_signed_layers():
    at = _open("hrv")
    for label, topic in (("SDNN", LT.SIGNED_HRV_SDNN), ("RMSSD", LT.SIGNED_HRV_RMSSD), ("pNN50", LT.SIGNED_HRV_PNN50)):
        exp = next(e for e in at.expander if e.label == f"¿Qué significa {label}?")
        inside = " ".join(m.value for m in exp.markdown) + " ".join(c.value for c in exp.caption)
        assert topic.mechanism in inside and "Fuente: [SG2017]" in inside, label
    emg = _open("emg")
    rms = next(e for e in emg.expander if e.label == "¿Qué significa RMS del EMG?")
    assert LT.SIGNED_EMG_A5.idea in " ".join(m.value for m in rms.markdown)


# ── PARTE B ────────────────────────────────────────────────────────────────────────────────────────────────────────
# Lo que [B2013] refuta: leer LF/HF como balance o dominancia. (El motivo de «Índice de estrés: no disponible» nombra
# la razón para explicar por qué ya no se calcula; se comprueba aparte que el índice no se muestra.)
LF_HF_CLAIM = re.compile(r"balance|dominancia|proxy", re.IGNORECASE)


def test_lf_hf_is_labeled_and_never_read_as_balance_on_the_hrv_and_biomarker_pages():
    for url in ("hrv", "biomarcadores"):
        texts = [t for t in _texts(_open(url)) if "LF/HF" in t]
        assert texts, url
        for t in texts:
            assert not LF_HF_CLAIM.search(t), (url, t[:160])
    hrv = " ".join(_texts(_open("hrv")))
    assert "razón LF/HF (interpretación discutida) [B2013]" in hrv
    bio = " ".join(_texts(_open("biomarcadores")))
    assert "Razón LF/HF (interpretación discutida)" in bio and "Índice de Estrés" not in bio
    assert "Índice de estrés — No disponible: se calculaba solo con la razón LF/HF" in bio


def test_the_narrator_receives_the_labeled_lf_hf_and_the_signed_meanings():
    src = Path(MAIN).read_text(encoding="utf-8")
    # T2 (2026-11-18): el espectro de la HRV vive en `app/instruments/hrv.py`; la guardia mira los dos archivos.
    code = "\n".join(l for l in (src + Path("app/instruments/hrv.py").read_text(encoding="utf-8")).splitlines()
                     if not l.lstrip().startswith("#"))
    assert "proxy de balance" not in code and "indicador vagal" not in code and "tono parasimpático'" not in code
    body = src[src.index("def render_hrv_page"):src.index("def render_patient_pipeline_page")]
    assert "f'{LF_HF_LABEL} [B2013]. ' + LF_HF_DISCUSSED" in body
    assert LT.LF_HF_LABEL == "razón LF/HF (interpretación discutida)" and "[B2013]" in LT.LF_HF_DISCUSSED


# Afirmaciones que deducen la fuerza de la amplitud (la negación «no mide cuánto contraes» es correcta y se queda).
EMG_FORCE_CLAIM = re.compile(r"saber cu[aá]nto contraes|sube con la fuerza|crece con la contracci|mira el RMS",
                             re.IGNORECASE)


def test_emg_never_deduces_force_effort_hypertrophy_diagnosis_or_injury_from_amplitude():
    at = _open("emg")
    texts = _texts(at)
    joined = " ".join(texts)
    assert not EMG_FORCE_CLAIM.search(joined), EMG_FORCE_CLAIM.search(joined)
    assert LT.SIGNED_EMG_A1.detail in joined                                  # la excitación, no la fuerza [V2018]
    for t in texts:
        if re.search(r"hipertrof", t, re.IGNORECASE):
            assert "**No** predice la hipertrofia" in t or "No predice la hipertrofia" in t, t[:160]
    for path in ("hardware/biosensors/sensors.py", "app/supermodules/biosensors/emg.py"):
        code = "\n".join(l for l in Path(path).read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        assert not EMG_FORCE_CLAIM.search(code), path


def test_hrv_has_no_posture_drug_exercise_attribution_nor_unsourced_normal_values():
    joined = " ".join(_texts(_open("hrv")))
    for bad in ("enfermedad crónica", "tono vagal eleva", "postura", "fármaco", "ejercicio"):
        assert bad not in joined.lower(), bad
    bio = " ".join(_texts(_open("biomarcadores")))
    assert "rango fisiológico correcto" not in bio


STEMI_NAMES = ("🔴 STEMI con elevación del ST en V1–V4", "🔴 STEMI con elevación del ST en II, III y aVF",
               "🔴 STEMI con elevación del ST en I, aVL, V5–V6")


def test_stemi_scenarios_are_named_by_what_the_trace_shows_and_interpreted_in_the_correction():
    from src.signals.ecg.twelve_lead_synth import generate_twelve_lead

    for name, scenario in zip(STEMI_NAMES, ("anterior_stemi", "inferior_stemi", "lateral_stemi")):
        _, truth = generate_twelve_lead(scenario, 75, 10.0, 500.0, seed=0)
        up = [ld for ld, v in truth.st_j_mv.items() if v >= 0.1]
        named = re.findall(r"aV[RLF]|V\d|I{1,3}", name.split("en ", 1)[1].replace("V1–V4", "V1 V2 V3 V4")
                           .replace("V5–V6", "V5 V6"))
        assert sorted(named) == sorted(up), (name, up)                    # el nombre dice lo que se construyó

    def _script():
        import app.supermodules.ecg_12.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=120)
    box = next(b for b in at.selectbox if "Escenario" in b.label)
    for name in STEMI_NAMES:
        assert name in box.options
    assert not [o for o in box.options if re.search(r"\((DA|CD o Cx)\)|Infarto (anterior|inferior|lateral)", o)]
    box.set_value(STEMI_NAMES[1])
    next(b for b in at.button if "Generar ECG" in b.label).click()
    at.run(timeout=120)
    assert at.exception == []
    corr = next(e for e in at.expander if e.label.startswith("Corrección del caso"))
    inside = " ".join(m.value for m in corr.markdown)
    assert "II, III, aVF" in inside and "Coronaria derecha (CD) o circunfleja (Cx)" in inside
    assert LT.ISCHEMIA_WARNING in inside


def test_per_value_hrv_topics_are_literal_lines_of_the_signed_document():
    """SDNN/RMSSD/pNN50 no están en Aprender (son el «¿Qué significa…?» del lab): su texto se comprueba aquí con la
    misma normalización que `test_fase1_t2_teoria.py`."""
    from test_fase1_t2_teoria import _norm

    doc = _norm(DOC2)
    for topic in (LT.SIGNED_HRV_SDNN, LT.SIGNED_HRV_RMSSD, LT.SIGNED_HRV_PNN50):
        for layer in (topic.idea, topic.mechanism):
            assert _norm(layer) in doc, (topic.title, layer)
