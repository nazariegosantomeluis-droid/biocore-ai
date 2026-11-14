"""EEG en vivo para el EEG Neuro Lab (2026-11-14): OpenBCI, Muse, Unicorn, cualquier flujo LSL y dos simuladores.

- `devices`: el catálogo (cómo se conecta cada uno, sus canales y su procedencia).
- `backends`: cómo se abre cada fuente (BrainFlow, LSL o el simulador de práctica).
- `simulator`: el EEG simulado de la práctica (ojos, parpadeo, electrodo flojo, cable).
- `service`: el hilo que lee, guarda los últimos segundos y dice en qué estado está.
- `quality`: filtro de la red y revisión de calidad por canal (heurísticas de ingeniería).
- `montage`: posiciones 10-20 y 10-10 para el diagrama del tutorial.

BrainFlow y pylsl son opcionales: sin ellos, el catálogo dice qué falta instalar y lo demás sigue funcionando.
"""

from .backends import (Backend, BackendError, BrainFlowBackend, LslBackend, LslStreamChoice, SimulatorBackend,
                       StreamDescription, discover_lsl_streams)
from .devices import (DEVICES, NO_VERIFICABLE, SENSOR_REAL, SIMULACION, EegDevice, backend_unavailable_reason,
                      get_device)
from .quality import ChannelQuality, QualityHeuristics, assess_channels, prepare
from .service import EegLiveService, LiveConfig, LiveState
from .simulator import SimulatedEegDevice

__all__ = [
    'Backend', 'BackendError', 'BrainFlowBackend', 'ChannelQuality', 'DEVICES', 'EegDevice', 'EegLiveService',
    'LiveConfig', 'LiveState', 'LslBackend', 'LslStreamChoice', 'NO_VERIFICABLE', 'QualityHeuristics',
    'SENSOR_REAL', 'SIMULACION', 'SimulatedEegDevice', 'SimulatorBackend', 'StreamDescription', 'assess_channels',
    'backend_unavailable_reason', 'discover_lsl_streams', 'get_device', 'prepare',
]
