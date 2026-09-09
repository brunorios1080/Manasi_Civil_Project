"""Independent balances, limiting cases, and analytical numerical checks."""
import json
import math
from pathlib import Path
import unittest

import numpy as np
from scipy.integrate import quad

from stormwater.hydrology import (cumulative_excess, load_ordinates, make_event,
                                 rainfall_increments, unit_hydrograph_weights)
from stormwater.routing import drawdown_hours, outlet_flow, route

ROOT = Path(__file__).resolve().parents[1]


class HydrologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "inputs/config.json").read_text())
        cls.ordinates = load_ordinates(ROOT / "inputs/scs_dimensionless_uh.csv")

    def test_all_rain_shapes_and_partial_blocks(self):
        for shape, weights in self.config["rainfall_weights"].items():
            for dt in (30, 15, 7.5, 37):
                rain = rainfall_increments(50, 3600, weights, dt)
                self.assertAlmostEqual(float(rain.sum()), 50, places=12)
                self.assertTrue(np.all(rain >= 0), shape)
        self.assertGreater(rainfall_increments(50, 3600, [6,5,4,3,2,1], 30)[0],
                           rainfall_increments(50, 3600, [6,5,4,3,2,1], 30)[-1])

    def test_cn_independent_decimal_check(self):
        # Direct scalar arithmetic, not the model's incremental calculation.
        from decimal import Decimal, getcontext
        getcontext().prec = 40
        s = Decimal(25400) / Decimal(98) - Decimal(254)
        x = Decimal(50) - Decimal("0.2") * s
        expected = float(x * x / (x + s))
        self.assertAlmostEqual(float(cumulative_excess(50)), expected, places=12)

    def test_zero_and_abstraction(self):
        self.assertEqual(float(cumulative_excess(0)), 0)
        self.assertEqual(float(cumulative_excess(0.5)), 0)
        event = make_event(self.config, 0.5, "uniform", self.ordinates)
        self.assertEqual(event.parking_inflow_m3.sum(), 0)
        self.assertAlmostEqual(event.direct_rain_m3.sum(), 0.1)

    def test_cn100(self):
        np.testing.assert_array_equal(cumulative_excess([0, 1, 50], 100), [0, 1, 50])

    def test_event_differencing_and_tail(self):
        for shape in self.config["rainfall_weights"]:
            event = make_event(self.config, 50, shape, self.ordinates)
            self.assertAlmostEqual(event.excess_mm.sum() * 4, event.expected_parking_m3, places=10)
            self.assertAlmostEqual(event.parking_inflow_m3.sum(), event.expected_parking_m3, places=10)
            self.assertGreater(event.inflow_tail_end_s, 3600)
            self.assertLess(event.inflow_tail_end_s, len(event.rain_mm) * event.dt)

    def test_single_pulse_timing_volume_full_tail(self):
        for dt in (30, 15, 7.5):
            weights = unit_hydrograph_weights(10, dt, self.ordinates)
            pulse_volume = 4.0
            hydrograph = np.convolve([pulse_volume], weights) / dt
            self.assertAlmostEqual(hydrograph.sum() * dt, pulse_volume, places=12)
            peak_s = (np.argmax(hydrograph) + 0.5) * dt
            self.assertLessEqual(abs(peak_s - (600 + dt / 2)), dt)
            self.assertGreaterEqual(len(weights) * dt, 5 * (600 + dt / 2))
            self.assertGreater(weights[-1], 0)

    def test_invalid_inputs(self):
        for cn in (0, -5, 101):
            with self.assertRaises(ValueError):
                cumulative_excess(50, cn)
        with self.assertRaises(ValueError):
            rainfall_increments(50, 3600, [0, 0], 30)


class RoutingTests(unittest.TestCase):
    def test_empty_zero_rainfall(self):
        result = route(np.zeros(100), 30, 200, 120, 0.08)
        self.assertEqual(result.storage_m3.sum(), 0)
        self.assertEqual(result.downstream_m3_s.sum(), 0)
        self.assertEqual(result.balance_error_m3, 0)

    def test_blocked_outlet_and_overflow(self):
        result = route(np.ones(10), 30, 200, 5, 0.0)
        self.assertEqual(result.storage_m3[-1], 5)
        self.assertEqual(result.controlled_m3_s.sum(), 0)
        self.assertAlmostEqual(result.overflow_m3_s.sum() * 30, 5)
        self.assertAlmostEqual(result.balance_error_m3, 0)
        self.assertIsNone(drawdown_hours(result.storage_m3, 30, 0, 5))

    def test_insufficient_storage_keeps_water(self):
        result = route([100, 0, 0], 30, 200, 10, 0.04)
        self.assertGreater(result.overflow_m3_s.sum() * 30, 89)
        self.assertLessEqual(result.storage_m3.max(), 10)
        self.assertGreaterEqual(result.storage_m3.min(), 0)
        self.assertLess(abs(result.balance_error_m3), 1e-9)

    def test_rating_by_independent_quadrature(self):
        for side in (0.04, 0.1):
            for h in (0, 0.001, side / 2, side, 0.3, 0.9):
                expected = quad(lambda z: 0.62 * side * math.sqrt(2 * 9.80665 * (h - z)),
                                0, min(h, side), epsabs=1e-12)[0]
                self.assertAlmostEqual(outlet_flow(h, side), expected, places=10)

    def test_deep_orifice_centroid_approximation(self):
        for side in (0.04, 0.06, 0.08, 0.1):
            head = 0.9
            conventional = 0.62 * side**2 * math.sqrt(2 * 9.80665 * (head - side / 2))
            self.assertLess(abs(outlet_flow(head, side) / conventional - 1), 0.001)

    def test_rating_monotonic_continuous(self):
        flows = [outlet_flow(h, 0.08) for h in np.linspace(0, 1, 1001)]
        self.assertTrue(np.all(np.diff(flows) >= 0))
        self.assertAlmostEqual(outlet_flow(0.08 - 1e-10, 0.08),
                               outlet_flow(0.08 + 1e-10, 0.08), places=9)

    def test_analytical_shallow_drainage_converges(self):
        # h < side throughout: A dh/dt = -k h^(3/2), exact solution below.
        area, h0, side, duration = 200.0, 0.02, 0.06, 3600.0
        k = (2 / 3) * 0.62 * side * math.sqrt(2 * 9.80665)
        exact_h = (h0**-0.5 + k * duration / (2 * area))**-2
        errors = []
        for dt in (30, 15, 7.5):
            result = route(np.zeros(int(duration / dt)), dt, area, 120, side,
                           initial_storage_m3=area * h0)
            errors.append(abs(result.storage_m3[-1] / area / exact_h - 1))
            self.assertLess(abs(result.balance_error_m3), 1e-9)
            self.assertTrue(np.all(np.diff(result.storage_m3) <= 0))
        self.assertLess(errors[2], 0.002)
        self.assertLess(errors[2], errors[1])
        self.assertLess(errors[1], errors[0])

    def test_drawdown_uses_final_crossing(self):
        # Threshold is 1 m3; first crossing is followed by a rebound.
        self.assertAlmostEqual(drawdown_hours([2, 0, 2, 0], 3600, 3600, 100), 1.5)
        self.assertEqual(drawdown_hours([0, 0], 30, 3600, 100), 0)
        self.assertIsNone(drawdown_hours([2, 1], 30, 0, 100))

    def test_step_equation_and_mass_balance(self):
        inflow = np.random.default_rng(42).uniform(0, 2, 600)
        result = route(inflow, 30, 200, 120, 0.08)
        residuals = np.diff(result.storage_m3) - inflow + result.downstream_m3_s * 30
        self.assertLess(np.max(np.abs(residuals)), 1e-9)
        self.assertLess(abs(result.balance_error_m3), 1e-8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
