"""Shared definitions for the v0.7 eight-method comparison (docs/PROTOCOL_v0.7.md). Frozen by the protocol."""
import os

import numpy as np

from experiments.v06_common import (git_state, run_tasks, sha256, verify_manifest, versions,  # noqa: F401
                                    write_json, write_manifest, IsolationError, assert_seeds)
from tccer.config import load_config, replace

TUNING_SEEDS = tuple(range(200, 220))
DEV_SEEDS = tuple(range(300, 320))          # development / smoke tests only; never reported as results
EVAL_SEEDS = tuple(range(7000, 7060))       # held-out; used exactly once by run_v07 --mode eval
SMOKE_CAL_SEEDS = (300, 301)
SMOKE_EVAL_SEEDS = (302, 303)

SCENARIOS = ("S1_rgg40_bursty", "S2_rgg40_background", "S3_rgg80_bursty")
BUDGETS = (3, 6)
DELAY = 2
CELLS = tuple((s, M) for s in SCENARIOS for M in BUDGETS)
SCENARIO_DIR = "configs/v0.7/scenarios"

ARM_POLICY = {"A0": "static", "A1": "v06_reactive", "A2": "v06_movavg", "A3": "v06_cusum_e",
              "A4": "v06_cusum_ecv", "A5": "v06_tccer", "A6": "v06_random", "A7": "v06_front"}
EVAL_ARMS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")
CALIBRATED_ARMS = ("A1", "A2", "A3", "A4", "A5")
ARM_KAPPA = {"A3": "kappa_E", "A4": "kappa_s", "A5": "kappa_s"}
GRID = {"A1": np.linspace(0.30, 0.98, 40), "A2": np.linspace(0.30, 0.98, 40),
        "A3": np.geomspace(0.05, 20.0, 40), "A4": np.geomspace(0.05, 20.0, 40), "A5": np.geomspace(0.05, 20.0, 40)}
SMOKE_GRID_POINTS = 6
FEASIBILITY = 0.15
TAU_QUANTILE = 0.75

FROZEN_DIR = "configs/v0.7/frozen"


def scenario_config(scenario):
    return replace(load_config(os.path.join(SCENARIO_DIR, f"{scenario}.yaml")), link_setup_epochs=DELAY,
                   mutation_cap=None)


def cell_name(scenario, M):
    return f"{scenario}_M{M}"


def frozen_path(frozen_dir, arm, scenario, M=None):
    if arm == "A0":
        return os.path.join(frozen_dir, f"A0_{scenario}.yaml")
    return os.path.join(frozen_dir, f"{arm}_{cell_name(scenario, M)}.yaml")


def grid(arm, smoke):
    g = GRID[arm]
    return g[np.linspace(0, len(g) - 1, SMOKE_GRID_POINTS).round().astype(int)] if smoke else g
