"""Interval-volume hydrology; all rainfall and runoff depths are in mm."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def cumulative_excess(precipitation_mm, cn=98.0, abstraction_ratio=0.2):
    """CN losses occur once per event, never independently at each step."""
    if not 0 < cn <= 100 or abstraction_ratio < 0:
        raise ValueError("CN must be in (0, 100] and abstraction ratio nonnegative")
    p = np.asarray(precipitation_mm, dtype=float)
    if np.any(p < 0):
        raise ValueError("Cumulative rainfall must be nonnegative")
    retention = 25400.0 / cn - 254.0
    if retention == 0:
        return p.copy()
    available = np.maximum(p - abstraction_ratio * retention, 0.0)
    return available**2 / (available + retention)


def rainfall_increments(depth_mm, duration_s, weights, dt):
    """Integrate constant-intensity blocks, including partially cut intervals."""
    w = np.asarray(weights, dtype=float)
    if depth_mm < 0 or duration_s <= 0 or dt <= 0:
        raise ValueError("Rain depth must be nonnegative; duration and step positive")
    if len(w) == 0 or np.any(w < 0) or w.sum() <= 0:
        raise ValueError("Rainfall weights must be nonnegative with positive sum")
    block_edges = np.linspace(0, duration_s, len(w) + 1)
    block_cumulative = np.r_[0.0, np.cumsum(w / w.sum()) * depth_mm]
    block_cumulative[-1] = depth_mm
    edges = np.arange(int(np.ceil(duration_s / dt)) + 1) * dt
    cumulative = np.interp(edges, block_edges, block_cumulative)
    increments = np.diff(cumulative)
    increments[-1] += depth_mm - increments.sum()
    return increments


def load_ordinates(path):
    table = np.loadtxt(Path(path), delimiter=",", skiprows=1)
    x, y = table.T
    if (len(x) < 3 or x[0] != 0 or y[0] != 0 or y[-1] != 0
            or np.any(np.diff(x) <= 0) or np.any(y < 0)
            or not np.isclose(x[np.argmax(y)], 1.0)):
        raise ValueError("Invalid dimensionless unit hydrograph reference")
    return x, y


def unit_hydrograph_weights(lag_min, dt, ordinates):
    """Exact bin integrals of the piecewise-linear reference, normalized to one.

    A pulse begins at t=0 and lasts dt. Tp = lag + dt/2. Each returned
    weight is the fraction arriving in [j*dt, (j+1)*dt). The entire 5*Tp
    reference tail is retained. q/qp is only a shape, not a flow unit.
    """
    if lag_min <= 0 or dt <= 0:
        raise ValueError("Lag and time step must be positive")
    x, y = ordinates
    tp = lag_min * 60.0 + dt / 2
    edges = np.arange(int(np.ceil(x[-1] * tp / dt)) + 1) * dt / tp
    slopes = np.diff(y) / np.diff(x)
    cumulative = np.r_[0.0, np.cumsum(np.diff(x) * (y[:-1] + y[1:]) / 2)]
    clipped = np.minimum(edges, x[-1])
    index = np.clip(np.searchsorted(x, clipped, side="right") - 1, 0, len(x) - 2)
    distance = clipped - x[index]
    integral = cumulative[index] + y[index] * distance + slopes[index] * distance**2 / 2
    weights = np.maximum(np.diff(integral), 0.0)
    weights /= weights.sum()
    return weights


@dataclass
class Event:
    event_id: str
    depth_mm: float
    shape: str
    dt: float
    duration_s: float
    rain_mm: np.ndarray
    excess_mm: np.ndarray
    parking_inflow_m3: np.ndarray
    direct_rain_m3: np.ndarray
    expected_parking_m3: float
    runoff_generation_error_m3: float
    transform_error_m3: float
    inflow_tail_end_s: float

    @property
    def inflow_m3(self):
        return self.parking_inflow_m3 + self.direct_rain_m3

    @property
    def baseline_m3_s(self):
        return self.inflow_m3 / self.dt

    @property
    def time_edges_s(self):
        return np.arange(len(self.rain_mm) + 1) * self.dt


def make_event(config, depth_mm, shape, ordinates, dt=None, horizon_h=None):
    dt = float(dt if dt is not None else config["time_step_s"])
    duration = config["rainfall_duration_min"] * 60.0
    rain = rainfall_increments(depth_mm, duration, config["rainfall_weights"][shape], dt)
    cumulative = np.r_[0.0, np.cumsum(rain)]
    excess = np.diff(cumulative_excess(cumulative, config["curve_number"], config["abstraction_ratio"]))
    parking_volumes = excess * config["parking_area_m2"] / 1000
    weights = unit_hydrograph_weights(config["lag_min"], dt, ordinates)
    transformed = np.convolve(parking_volumes, weights, mode="full")
    expected = float(cumulative_excess(depth_mm, config["curve_number"], config["abstraction_ratio"])) * config["parking_area_m2"] / 1000
    horizon_h = config["horizon_h"] if horizon_h is None else horizon_h
    n = max(int(np.ceil(horizon_h * 3600 / dt)), len(transformed))
    def pad(a):
        return np.pad(a, (0, n - len(a)))
    nonzero = np.flatnonzero(transformed)
    return Event(
        f"{depth_mm:g}mm_{shape}", float(depth_mm), shape, dt, duration,
        pad(rain), pad(excess), pad(transformed),
        pad(rain * config["basin_area_m2"] / 1000), expected,
        float(parking_volumes.sum() - expected),
        float(transformed.sum() - parking_volumes.sum()),
        float((nonzero[-1] + 1) * dt) if len(nonzero) else 0.0,
    )
