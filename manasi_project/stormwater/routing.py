"""Mass-conserving backward Euler storage routing with explicit overflow."""
from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq


def outlet_flow(h, side_m, cd=0.62, gravity=9.80665):
    """Vertically integrated square opening, with sill at the floor.

    The partially wetted region is included; h is above the sill, not the
    opening centroid. No tailwater, evaporation, or infiltration is modeled.
    """
    if h <= 0 or side_m == 0 or cd == 0:
        return 0.0
    if side_m < 0 or cd < 0 or gravity <= 0:
        raise ValueError("Invalid outlet parameters")
    return (2 / 3) * cd * side_m * math.sqrt(2 * gravity) * (
        h**1.5 - max(h - side_m, 0.0)**1.5
    )


@dataclass
class Routing:
    storage_m3: np.ndarray
    controlled_m3_s: np.ndarray
    overflow_m3_s: np.ndarray
    dt: float

    @property
    def downstream_m3_s(self):
        return self.controlled_m3_s + self.overflow_m3_s

    @property
    def balance_error_m3(self):
        return self._balance_error_m3


def route(inflow_m3, dt, area_m2, capacity_m3, side_m, cd=0.62,
          gravity=9.80665, initial_storage_m3=0.0):
    inflow = np.asarray(inflow_m3, dtype=float)
    if (dt <= 0 or area_m2 <= 0 or capacity_m3 <= 0 or side_m < 0 or cd < 0
            or gravity <= 0 or not 0 <= initial_storage_m3 <= capacity_m3
            or not np.all(np.isfinite(inflow)) or np.any(inflow < 0)):
        raise ValueError("Invalid routing inputs")
    storage = np.empty(len(inflow) + 1)
    controlled = np.zeros(len(inflow))
    overflow = np.zeros(len(inflow))
    storage[0] = initial_storage_m3
    factor = (2 / 3) * cd * side_m * math.sqrt(2 * gravity)
    def rating(s):
        h = s / area_m2
        return factor * (h**1.5 - max(h - side_m, 0.0)**1.5)
    qcap = rating(capacity_m3)
    for i, volume in enumerate(inflow):
        available = storage[i] + volume
        if available == 0.0:
            storage[i + 1] = 0.0
        elif available >= capacity_m3 + dt * qcap:
            storage[i + 1] = capacity_m3
            controlled[i] = qcap
            overflow[i] = max((available - capacity_m3) / dt - qcap, 0.0)
        elif factor == 0.0:
            storage[i + 1] = available
        else:
            s = brentq(lambda v: v + dt * rating(v) - available,
                       0.0, min(capacity_m3, available), xtol=1e-12, rtol=1e-12)
            storage[i + 1] = s
            controlled[i] = rating(s)
    result = Routing(storage, controlled, overflow, dt)
    result._balance_error_m3 = float(initial_storage_m3 + inflow.sum()
        - dt * (controlled.sum() + overflow.sum()) - storage[-1])
    return result


def drawdown_hours(storage, dt, rain_end_s, capacity, fraction=0.01):
    """Final crossing below threshold after rain ends, with no later rebound.

    Crossings are linearly interpolated between state times. None means the
    simulated event never establishes drainage below the threshold. Exact
    equality is still above because the criterion is strictly 'below'.
    """
    threshold = fraction * capacity
    above = np.flatnonzero(np.asarray(storage) >= threshold)
    if len(above) == 0:
        return 0.0
    last = int(above[-1])
    if last == len(storage) - 1:
        return None
    crossing_s = (last + (storage[last] - threshold) /
                  (storage[last] - storage[last + 1])) * dt
    return float(max(0.0, (crossing_s - rain_end_s) / 3600))
