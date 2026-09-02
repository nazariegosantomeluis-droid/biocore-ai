import os
import numpy as np
import importlib.util
import os
import numpy as np


def _load_classifier():
    p = os.path.join(os.path.dirname(__file__), os.pardir, "biomedical", "arrhythmia_classifier.py")
    p = os.path.abspath(p)
    spec = importlib.util.spec_from_file_location("biomedical.arrhythmia_classifier", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ArrhythmiaClassifier


def test_arrhythmia_classifier_smoke(tmp_path):
    ArrhythmiaClassifier = _load_classifier()
    ac = ArrhythmiaClassifier(model_dir=str(tmp_path))
    # generate tiny synthetic dataset
    t = np.linspace(0, 1, 150)
    segs = []
    labels = []
    for i in range(10):
        segs.append(np.sin(2 * np.pi * 5 * t) + 0.01 * np.random.randn(t.size))
        labels.append("Normal")
    for i in range(10):
        segs.append(np.sign(np.sin(2 * np.pi * 7 * t)) + 0.01 * np.random.randn(t.size))
        labels.append("PVC")

    results = ac.train(segs, labels, test_size=0.2)
    assert isinstance(results, dict)
    # saved model should exist for random_forest
    p = os.path.join(str(tmp_path), "random_forest.pkl")
    assert os.path.exists(p)
