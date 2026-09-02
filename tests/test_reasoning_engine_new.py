import os
import importlib.util
import os


def _load_engine():
    p = os.path.join(os.path.dirname(__file__), os.pardir, "biomedical", "reasoning_engine.py")
    p = os.path.abspath(p)
    spec = importlib.util.spec_from_file_location("biomedical.reasoning_engine", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BiomedicalReasoningEngine


def test_reasoning_engine_basic():
    BiomedicalReasoningEngine = _load_engine()
    engine = BiomedicalReasoningEngine()
    metrics = {"BPM": 112, "RMSSD": 18, "LF/HF": 3.5, "Entropy": 2.0}
    out = engine.analyze(metrics, ia_result={"label": "AFib", "probability": 0.85})
    assert isinstance(out, dict)
    assert "hallazgos" in out
    assert "hipotesis" in out
    assert "diagnosticos_diferenciales" in out
    assert "riesgo" in out
    assert "explicacion" in out
