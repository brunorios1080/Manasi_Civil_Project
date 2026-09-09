"""Scenario sweep, fixed-rule selection, convergence, and sensitivity."""
from dataclasses import asdict
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .hydrology import make_event
from .routing import drawdown_hours, route


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def design_id(depth, side_mm):
    return f"h{depth:.3f}_o{side_mm:g}"


def base_metrics(event, config):
    flow = event.baseline_m3_s
    return {
        "event_id": event.event_id, "rainfall_mm": event.depth_mm, "shape": event.shape,
        "dt_s": event.dt, "horizon_h": len(flow) * event.dt / 3600,
        "curve_number": config["curve_number"], "lag_min": config["lag_min"],
        "discharge_coefficient": config["discharge_coefficient"],
        "rainfall_total_mm": float(event.rain_mm.sum()),
        "parking_runoff_m3": float(event.parking_inflow_m3.sum()),
        "direct_rain_m3": float(event.direct_rain_m3.sum()),
        "total_inflow_m3": float(event.inflow_m3.sum()),
        "runoff_generation_error_m3": event.runoff_generation_error_m3,
        "transform_error_m3": event.transform_error_m3,
        "inflow_tail_end_h": event.inflow_tail_end_s / 3600,
        "baseline_peak_m3_s": float(flow.max()),
        "baseline_time_to_peak_min": float((np.argmax(flow) + 0.5) * event.dt / 60),
    }


def simulate_case(config, event, depth, side_mm, ordinates):
    started = time.perf_counter()
    capacity = config["basin_area_m2"] * depth
    while True:
        routed = route(event.inflow_m3, event.dt, config["basin_area_m2"], capacity,
                       side_mm / 1000, config["discharge_coefficient"],
                       config["gravity_m_s2"], config["initial_storage_m3"])
        drawdown = drawdown_hours(routed.storage_m3, event.dt, event.duration_s,
                                  capacity, config["drawdown_fraction"])
        current_h = len(event.rain_mm) * event.dt / 3600
        if drawdown is not None or side_mm == 0 or config["discharge_coefficient"] == 0:
            break
        if current_h >= config["max_horizon_h"]:
            break
        event = make_event(config, event.depth_mm, event.shape, ordinates, event.dt,
                           min(current_h * 2, config["max_horizon_h"]))
    row = base_metrics(event, config)
    downstream = routed.downstream_m3_s
    peak = float(downstream.max())
    baseline = row["baseline_peak_m3_s"]
    reduction = 100 * (1 - peak / baseline) if baseline > 0 else 0.0
    overflow = float(routed.overflow_m3_s.sum() * event.dt)
    overflowing = np.flatnonzero(routed.overflow_m3_s * event.dt > 1e-12)
    row.update({
        "design_id": design_id(depth, side_mm), "storage_depth_m": depth,
        "capacity_m3": capacity, "outlet_side_mm": float(side_mm),
        "peak_downstream_m3_s": peak, "peak_reduction_pct": reduction,
        "time_to_peak_min": float((np.argmax(downstream) + 0.5) * event.dt / 60),
        "maximum_storage_m3": float(routed.storage_m3.max()),
        "maximum_depth_m": float(routed.storage_m3.max() / config["basin_area_m2"]),
        "overflow_m3": overflow,
        "overflow_onset_min": float(overflowing[0] * event.dt / 60) if len(overflowing) else None,
        "controlled_discharge_m3": float(routed.controlled_m3_s.sum() * event.dt),
        "total_discharge_m3": float(downstream.sum() * event.dt),
        "residual_storage_m3": float(routed.storage_m3[-1]),
        "drawdown_h_after_rain": drawdown,
        "routing_balance_error_m3": routed.balance_error_m3,
        "routing_balance_relative_error": abs(routed.balance_error_m3) / max(row["total_inflow_m3"], 1e-30),
        "peak_pass": reduction >= config["minimum_peak_reduction_pct"],
        "overflow_pass": overflow <= config["overflow_tolerance_m3"],
        "drawdown_pass": drawdown is not None and drawdown <= config["drawdown_limit_h"],
        "simulation_runtime_s": time.perf_counter() - started,
    })
    row["all_pass"] = bool(row["peak_pass"] and row["overflow_pass"] and row["drawdown_pass"])
    return row, event, routed


def save_case(directory, row, event, routed):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = f'{row["event_id"]}__{row["design_id"]}'
    np.savez_compressed(directory / (name + ".npz"),
        time_edges_s=event.time_edges_s, rain_mm=event.rain_mm,
        excess_mm=event.excess_mm, parking_inflow_m3=event.parking_inflow_m3,
        direct_rain_m3=event.direct_rain_m3, storage_m3=routed.storage_m3,
        controlled_m3_s=routed.controlled_m3_s, overflow_m3_s=routed.overflow_m3_s)
    write_json(directory / (name + ".json"), row)


def run_grid(config, ordinates, dt, save_directory=None):
    rows, baselines = [], []
    for rain in config["rainfall_depths_mm"]:
        for shape in config["rainfall_weights"]:
            event = make_event(config, rain, shape, ordinates, dt)
            baselines.append(base_metrics(event, config))
            for depth in config["storage_depths_m"]:
                for side in config["outlet_sides_mm"]:
                    row, used_event, routed = simulate_case(config, event, depth, side, ordinates)
                    rows.append(row)
                    if save_directory is not None:
                        save_case(save_directory, row, used_event, routed)
            print(f"  dt={dt:g}s: {rain:g} mm {shape} complete", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(baselines)


def select_design(cases, config):
    design_cases = cases[np.isclose(cases.rainfall_mm, config["design_rainfall_mm"])]
    rows = []
    for identity, group in design_cases.groupby("design_id", sort=False):
        if len(group) != len(config["rainfall_weights"]):
            raise ValueError("Selection requires every storm shape exactly once")
        rows.append({
            "design_id": identity, "capacity_m3": float(group.capacity_m3.iloc[0]),
            "storage_depth_m": float(group.storage_depth_m.iloc[0]),
            "outlet_side_mm": float(group.outlet_side_mm.iloc[0]),
            "all_design_storms_pass": bool(group.all_pass.all()),
            "worst_peak_reduction_pct": float(group.peak_reduction_pct.min()),
            "worst_overflow_m3": float(group.overflow_m3.max()),
            "worst_drawdown_h": float(group.drawdown_h_after_rain.max()) if group.drawdown_h_after_rain.notna().all() else None,
            "passing_shapes": int(group.all_pass.sum()),
        })
    table = pd.DataFrame(rows).sort_values(["capacity_m3", "outlet_side_mm"])
    feasible = table[table.all_design_storms_pass].sort_values(
        ["capacity_m3", "worst_drawdown_h", "worst_overflow_m3", "outlet_side_mm"],
        ascending=[True, True, True, False])
    winner = feasible.iloc[0].to_dict() if len(feasible) else None
    return winner, table


def compare_resolutions(coarse, fine, config):
    joined = coarse.merge(fine, on=["event_id", "design_id"], suffixes=("_coarse", "_fine"))
    rows = []
    for _, row in joined.iterrows():
        r = {"event_id": row.event_id, "design_id": row.design_id,
             "coarse_dt_s": row.dt_s_coarse, "fine_dt_s": row.dt_s_fine}
        for metric in ("peak_downstream_m3_s", "maximum_storage_m3", "baseline_peak_m3_s"):
            r[metric + "_relative_change"] = abs(row[metric + "_coarse"] - row[metric + "_fine"]) / max(abs(row[metric + "_fine"]), 1e-12)
        r["overflow_change_m3"] = abs(row.overflow_m3_coarse - row.overflow_m3_fine)
        r["overflow_onset_change_s"] = abs(row.overflow_onset_min_coarse - row.overflow_onset_min_fine) * 60
        r["overflow_classification_stable"] = bool(row.overflow_pass_coarse == row.overflow_pass_fine)
        r["drawdown_change_s"] = abs(row.drawdown_h_after_rain_coarse - row.drawdown_h_after_rain_fine) * 3600
        r["acceptance_stable"] = bool(row.all_pass_coarse == row.all_pass_fine)
        r["peak_storage_converged"] = all(r[m + "_relative_change"] < config["convergence_relative_tolerance"]
            for m in ("peak_downstream_m3_s", "maximum_storage_m3", "baseline_peak_m3_s"))
        rows.append(r)
    return pd.DataFrame(rows)


def run_sensitivity(config, ordinates, winner, dt, output):
    rows = []
    if winner is None:
        return pd.DataFrame()
    for parameter, values in config["sensitivity"].items():
        for value in values:
            variant = dict(config)
            variant[parameter] = value
            for shape in config["rainfall_weights"]:
                event = make_event(variant, config["design_rainfall_mm"], shape, ordinates, dt)
                row, event, routed = simulate_case(variant, event, winner["storage_depth_m"],
                                                   winner["outlet_side_mm"], ordinates)
                row.update({"varied_parameter": parameter, "parameter_value": value,
                            "is_nominal": value == config[parameter]})
                save_case(Path(output) / "sensitivity_series" / f"{parameter}_{value:g}", row, event, routed)
                rows.append(row)
    return pd.DataFrame(rows)


def independent_checks(config, ordinates):
    from scipy.integrate import quad
    from .routing import outlet_flow
    import math
    checks = {}
    outlet_rows = []
    for side_mm in config["outlet_sides_mm"]:
        side = side_mm / 1000
        for h in (side / 2, side, 0.3, 0.9):
            integrated = outlet_flow(h, side, config["discharge_coefficient"], config["gravity_m_s2"])
            quadrature = quad(lambda z: config["discharge_coefficient"] * side * math.sqrt(2 * config["gravity_m_s2"] * (h - z)),
                              0, min(h, side), epsabs=1e-12)[0]
            centroid = (config["discharge_coefficient"] * side**2 * math.sqrt(2 * config["gravity_m_s2"] * (h - side / 2))) if h >= side else None
            outlet_rows.append({"side_mm": side_mm, "head_m": h, "integrated_m3_s": integrated,
                "quadrature_m3_s": quadrature, "absolute_difference_m3_s": abs(integrated - quadrature),
                "centroid_m3_s": centroid,
                "centroid_relative_difference": abs(integrated / centroid - 1) if centroid else None})
    checks["outlet_checks"] = outlet_rows
    area, h0, side, duration = 200.0, 0.02, 0.06, 3600.0
    k = (2 / 3) * 0.62 * side * math.sqrt(2 * 9.80665)
    exact = (h0**-0.5 + k * duration / (2 * area))**-2
    checks["analytical_shallow_drainage"] = []
    for dt in (30.0, 15.0, 7.5):
        r = route(np.zeros(int(duration / dt)), dt, area, 120, side, initial_storage_m3=area * h0)
        checks["analytical_shallow_drainage"].append({"dt_s": dt, "exact_final_depth_m": exact,
            "computed_final_depth_m": float(r.storage_m3[-1] / area),
            "relative_error": float(abs(r.storage_m3[-1] / area / exact - 1))})
    return checks
