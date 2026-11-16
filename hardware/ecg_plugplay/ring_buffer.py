"""Buffer circular que entrega ventanas con solape.

Guarda las últimas `size` muestras de varios campos (señal, banderas, índice)
en arreglos de NumPy de tamaño fijo, sin crecer. Cada vez que llegan `hop`
muestras nuevas (y ya hay `size` acumuladas) entrega una ventana completa:
con size=1000 y hop=500 sale una ventana de 4 s cada 2 s (solape del 50 %).

Las ventanas siempre terminan exactamente en múltiplos de `hop`, aunque las
muestras lleguen en trozos de cualquier tamaño: si un trozo cruza dos límites,
salen dos ventanas.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np


class SlidingWindowBuffer:
    def __init__(self, size: int, hop: int, fields: Dict[str, type]) -> None:
        if size <= 0 or hop <= 0:
            raise ValueError('size y hop deben ser positivos.')
        self.size = int(size)
        self.hop = int(hop)
        self._dtypes = dict(fields)
        self._data = {name: np.zeros(self.size, dtype=dtype) for name, dtype in self._dtypes.items()}
        self.total = 0
        self._next_emit = self.size

    @property
    def filled(self) -> int:
        """Muestras disponibles (hasta `size`)."""
        return min(self.total, self.size)

    def clear(self) -> None:
        for arr in self._data.values():
            arr.fill(0)
        self.total = 0
        self._next_emit = self.size

    def extend(self, **arrays: np.ndarray) -> List[Dict[str, np.ndarray]]:
        """Agrega muestras (mismo largo en todos los campos) y devuelve las ventanas listas."""
        if set(arrays) != set(self._data):
            raise ValueError(f'Se esperaban los campos {sorted(self._data)}.')
        lengths = {len(a) for a in arrays.values()}
        if len(lengths) != 1:
            raise ValueError('Todos los campos deben traer el mismo número de muestras.')
        n = lengths.pop()
        windows: List[Dict[str, np.ndarray]] = []
        i = 0
        while i < n:
            take = min(n - i, self._next_emit - self.total)
            self._write({k: np.asarray(v)[i:i + take] for k, v in arrays.items()}, take)
            i += take
            if self.total == self._next_emit:
                windows.append(self._window())
                self._next_emit += self.hop
        return windows

    def _write(self, chunk: Dict[str, np.ndarray], n: int) -> None:
        if n <= 0:
            return
        if n > self.size:  # solo lo último cabe
            chunk = {k: v[-self.size:] for k, v in chunk.items()}
            self.total += n - self.size
            n = self.size
        start = self.total % self.size
        first = min(n, self.size - start)
        for name, values in chunk.items():
            arr = self._data[name]
            arr[start:start + first] = values[:first]
            if first < n:
                arr[:n - first] = values[first:n]
        self.total += n

    def _window(self) -> Dict[str, np.ndarray]:
        idx = np.arange(self.total - self.size, self.total) % self.size
        out = {name: arr[idx].copy() for name, arr in self._data.items()}
        out['start'] = np.int64(self.total - self.size)
        return out
