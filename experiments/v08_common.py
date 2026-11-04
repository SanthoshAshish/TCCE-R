"""Shared definitions for the v0.8 experiments (docs/PROTOCOL_v0.8.md). Reuses the v0.6/v0.7 machinery unchanged.

Seed separation (decided 2026-11-04; disjoint from every earlier range 0-7059):
  calibration 8000-8019 | development / E1 / smoke 8100-8119 | held-out evaluation 9000-9059
All outputs go under results/v0.8 (git-ignored) and configs/v0.8; nothing is ever written to v0.7 locations.
"""
import os

import numpy as np

from experiments.v07_common import (BUDGETS, CELLS, FEASIBILITY, SCENARIOS, TAU_QUANTILE, assert_seeds,  # noqa: F401
                                    cell_name, frozen_path, git_state, run_tasks, scenario_config, sha256,
                                    verify_manifest, versions, write_json, write_manifest)
from tccer.config import replace

TUNING_SEEDS = tuple(range(8000, 8020))
DEV_SEEDS = tuple(range(8100, 8120))                 # E1, smoke tests, development; never reported as results
EVAL_SEEDS = tuple(range(9000, 9060))                # held-out; used exactly once by run_v08 --mode eval
SMOKE_CAL_SEEDS = (8100, 8101)
SMOKE_EVAL_SEEDS = (8102, 8103)

FROZEN_DIR = "configs/v0.8/frozen"
SMOKE_FROZEN_DIR = "results/v0.8/smoke/frozen"
E2_OUT = "results/v0.8/E2/eval"
CAL_OUT = "results/v0.8/E2/calibration"
CALIBRATION_RUN_CAP = 12                              # calibration runs are capped (>= 2M); only counts near M matter

# arm label -> registered policy name. Professor's B-labels: B1 = A1, B5 = A4 evaluated at B8's threshold (section 6 of
# the protocol); P1 (predictive-only) is dropped: it answers no requirement of the brief.
ARM_POLICY = {"A0": "static", "A1": "v06_reactive", "A5": "v06_tccer", "A7": "v06_front", "A7M": "v06_front",
              "B2": "v08_b2", "B3": "v08_b3", "B4": "v08_b4", "B5": "v06_cusum_ecv", "B6": "v08_rcpr_fixed",
              "B7": "v08_rcpr_legacy", "B8": "v08_rcpr", "H1": "v08_hybrid"}
CALIBRATED_ARMS = ("A1", "A5", "B2", "B3", "B4", "B8")           # own threshold, tuned on mean mutation count only
DERIVED_FROM_B8 = ("B5", "B6", "B7", "H1")                        # same kappa, same threshold as B8: only one component differs
EVAL_ARMS = ("A1", "A5", "A7", "A7M", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "H1")
ARM_KAPPA = {"A5": "kappa_s", "B8": "kappa_s"}                    # CUSUM drift allowance (derived arms inherit B8's)
HYBRID_F = {3: 2, 6: 3}                                           # F = ceil(M / 2)

GRID_POINTS = 28
GRID = {"A1": np.linspace(0.30, 0.98, GRID_POINTS), "B2": np.linspace(0.05, 0.95, GRID_POINTS),
        "B3": np.linspace(0.05, 0.95, GRID_POINTS), "B4": np.linspace(0.05, 0.95, GRID_POINTS),
        "A5": np.geomspace(0.05, 20.0, GRID_POINTS), "B8": np.geomspace(0.05, 20.0, GRID_POINTS)}
SMOKE_GRID_POINTS = 6


def grid(arm, smoke):
    g = GRID[arm]
    return g[np.linspace(0, len(g) - 1, SMOKE_GRID_POINTS).round().astype(int)] if smoke else g


def arm_config(base, arm, thr, kappa, M, cap=None):
    """Config of a calibrated arm. cap: calibration runs use CALIBRATION_RUN_CAP, final configs use M."""
    return replace(base, v06_threshold=float(thr), mutation_cap=M if cap is None else cap,
                   v06_kappa=kappa[ARM_KAPPA[arm]] if arm in ARM_KAPPA else None)


def derive_from_b8(b8_cfg, M):
    """B5, B6, B7, H1 inherit B8's config exactly (same threshold, kappa, cap, scenario); the policy class supplies the
    one intended difference (B5: lexicographic selection; B6: no adaptation; B7: legacy feedback; H1: front phase)."""
    out = {a: b8_cfg for a in ("B5", "B6", "B7")}
    out["H1"] = replace(b8_cfg, v08_front=HYBRID_F[M])
    return out
