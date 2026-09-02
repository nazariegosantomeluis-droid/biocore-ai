"""Biomedical Reasoning Engine (duplicate under `biomedical` package).

This is a non-intrusive copy of the new reasoning engine that lives under a
separate package name to avoid import conflicts with existing project packages.
"""
from typing import Dict, Any, List, Optional


class BiomedicalReasoningEngine:
    DEFAULT_THRESHOLDS = {
        "tachycardia_bpm": 100,
        "bradycardia_bpm": 50,
        "low_rmssd": 20,
        "low_sdnn": 30,
        "high_lf_hf": 2.5,
        "high_entropy": 1.5,
    }

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    def _get(self, metrics: Dict[str, Any], keys: List[str], default=None):
        for k in keys:
            if k in metrics:
                return metrics[k]
            if k.lower() in metrics:
                return metrics[k.lower()]
            if k.upper() in metrics:
                return metrics[k.upper()]
        return default

    def analyze(self, metrics: Dict[str, float], ia_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        m = {k: float(v) for k, v in metrics.items() if v is not None}
        bpm = self._get(m, ["BPM", "bpm"], default=None)
        sdnn = self._get(m, ["SDNN", "sdnn"], default=None)
        rmssd = self._get(m, ["RMSSD", "rmssd"], default=None)
        lf_hf = self._get(m, ["LF/HF", "LF_HF", "lf_hf", "lf/hf"], default=None)
        entropy = self._get(m, ["Entropy", "entropy"], default=None)

        findings = []
        hypotheses = []
        differentials = []

        if bpm is not None:
            if bpm >= self.thresholds["tachycardia_bpm"]:
                findings.append(f"Taquicardia (BPM={bpm})")
            elif bpm <= self.thresholds["bradycardia_bpm"]:
                findings.append(f"Bradicardia (BPM={bpm})")
            else:
                findings.append(f"Frecuencia dentro de rango (BPM={bpm})")

        if rmssd is not None:
            if rmssd < self.thresholds["low_rmssd"]:
                findings.append(f"RMSSD reducido ({rmssd} ms) → pérdida de variabilidad vagal")
            else:
                findings.append(f"RMSSD en rango ({rmssd} ms)")

        if lf_hf is not None:
            if lf_hf > self.thresholds["high_lf_hf"]:
                findings.append(f"Predominio simpático (LF/HF={lf_hf})")
            else:
                findings.append(f"Balance autonómico dentro de rango (LF/HF={lf_hf})")

        if entropy is not None:
            if entropy > self.thresholds["high_entropy"]:
                findings.append(f"Alta entropía ({entropy}) → ritmo irregular o más caótico")
            else:
                findings.append(f"Entropía en rango ({entropy})")

        score = 0.0
        if bpm is not None and bpm >= self.thresholds["tachycardia_bpm"]:
            score += 1.0
        if rmssd is not None and rmssd < self.thresholds["low_rmssd"]:
            score += 1.0
        if lf_hf is not None and lf_hf > self.thresholds["high_lf_hf"]:
            score += 0.6
        if entropy is not None and entropy > self.thresholds["high_entropy"]:
            score += 1.2

        if entropy is not None and entropy > self.thresholds["high_entropy"] and rmssd is not None and rmssd < self.thresholds["low_rmssd"]:
            hypotheses.append("Fibrilación auricular (FA) posible — ritmo irregular con baja variabilidad y alta entropía")

        if ia_result:
            label = ia_result.get("label") or ia_result.get("prediction")
            prob = ia_result.get("probability") or ia_result.get("score")
            if label:
                findings.append(f"Resultado IA: {label} (score={prob})")
                if isinstance(label, str) and "af" in label.lower() and entropy is not None and entropy > self.thresholds["high_entropy"]:
                    hypotheses.append("IA apoya diagnóstico de Fibrilación Auricular")

        if any("Fibrilación" in h or "FA" in h for h in hypotheses):
            differentials.extend(["Fibrilación auricular paroxística", "Taquicardia supraventricular", "Flutter auricular"]) 
        else:
            if rmssd is not None and rmssd < self.thresholds["low_rmssd"]:
                differentials.extend(["Episodios de estrés agudo", "Uso de estimulantes (cafeína, simpatomiméticos)", "Afección autonómica"]) 

        risk_score = score
        if bpm is not None and bpm >= 140:
            risk_score += 1.5
        if entropy is not None and entropy > self.thresholds["high_entropy"]:
            risk_score += 1.0

        if risk_score >= 3.0:
            risk = "alto"
        elif risk_score >= 1.5:
            risk = "moderado"
        else:
            risk = "bajo"

        explanation_lines = []
        explanation_lines.append(f"Puntuación heurística: {risk_score:.2f} (umbrales adaptativos)")
        explanation_lines.append("Se combinan signos vitales, HRV y espectro para generar hipótesis clínicas explicables.")
        if findings:
            explanation_lines.append("Hallazgos clave: " + "; ".join(findings[:4]))

        explanation = " ".join(explanation_lines)

        return {
            "hallazgos": findings,
            "hipotesis": hypotheses,
            "diagnosticos_diferenciales": differentials,
            "riesgo": risk,
            "explicacion": explanation,
        }
