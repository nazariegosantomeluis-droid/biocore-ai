"""BIOCORE AI Engine Layer - Digital Twin Physiological Intelligence

This module exports all digital twin and physiological analysis engines.
"""

# Digital Twin Organism (Core System)
try:
    from .digital_twin_organism import (
        DigitalTwinOrganism,
        OrganSystem,
        OrganMetrics,
        OrganHealthStatus,
    )
except ImportError as e:
    print(f"Warning: Could not import DigitalTwinOrganism: {e}")

# NOTE: CausalityEngine/CausalEvent (causality_engine.py) fueron retirados el
# 2026-08-19 (Art. I, Capa 3 de honestidad) -- CAUSAL_RULES tenía confidence
# hardcodeado (0.75-0.95) por regla, sin cálculo. Reemplazado en la UI desde
# el 2026-07-13 por el narrador causal real (domain/physiology/narrator/causal.py,
# que reutiliza solo 2 de las 8 reglas como "reference_confidence" citado al
# modelo, nunca como dato crudo). Confirmado sin llamadores vivos antes de
# retirarlo -- ver CHANGELOG.md.

# Simulation Engine
try:
    from .simulation_engine import (
        SimulationEngine,
        SimulationScenario,
        SimulationTimestep,
    )
except ImportError as e:
    print(f"Warning: Could not import SimulationEngine: {e}")

# Prediction Engine
try:
    from .prediction_engine import (
        PredictionEngine,
        RiskAssessment,
        GlobalRiskAssessment,
    )
except ImportError as e:
    print(f"Warning: Could not import PredictionEngine: {e}")

# NOTE: PhysiologicalFusionEngine/OrganState/HealthStatus (physiological_fusion.py),
# DigitalTwinComponent (digital_twin_component.py), and DigitalTwinMultisystem
# (digital_twin_multisystem.py) were all retired during the 2026-07-01 engine
# consolidation. Their real computations (organ health scoring, system couplings,
# anomaly/alert detection, high-fidelity per-organ parameters, intervention/prediction
# simulation) were ported into DigitalTwinOrganism (organs[...].detail + the
# stress/recovery/sleep/performance cross-cutting states). See _archive/README.md.

__all__ = [
    # Digital Twin Organism (canonical)
    'DigitalTwinOrganism',
    'OrganSystem',
    'OrganMetrics',
    'OrganHealthStatus',

    # Simulation Engine
    'SimulationEngine',
    'SimulationScenario',
    'SimulationTimestep',

    # Prediction Engine
    'PredictionEngine',
    'RiskAssessment',
    'GlobalRiskAssessment',
]



