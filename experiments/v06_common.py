"""Shared definitions for the v0.6 experiment (docs/PROTOCOL_v0.6.md). Everything here is frozen by the protocol."""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from tccer.config import load_config, replace
from tccer.sim.engine import simulate

TUNING_SEEDS = tuple(range(100, 120))
EVAL_SEEDS = tuple(range(6000, 6060))
DELAYS = (2, 8)
BUDGETS = (3, 6)
CELLS = tuple((d, M) for d in DELAYS for M in BUDGETS)
BASE_CONFIG = "configs/v0.4/selected_d2.yaml"

ARM_POLICY = {"A0": "static", "A1": "v06_reactive", "A2": "v06_movavg", "A3": "v06_cusum_e",
              "A4": "v06_cusum_ecv", "A5": "v06_tccer", "A6": "v06_random", "A7": "v06_front",
              "A2r": "v06_movavg_reset"}
EVAL_ARMS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")       # A0 runs once per seed
CALIBRATED_ARMS = ("A1", "A2", "A3", "A4", "A5")
ARM_KAPPA = {"A3": "kappa_E", "A4": "kappa_s", "A5": "kappa_s"}

GRID = {"A1": np.linspace(0.30, 0.98, 40), "A2": np.linspace(0.30, 0.98, 40),
        "A3": np.geomspace(0.05, 20.0, 40), "A4": np.geomspace(0.05, 20.0, 40), "A5": np.geomspace(0.05, 20.0, 40)}
FEASIBILITY = 0.15                     # calibrated mean must be within +-15% of M
TAU_QUANTILE = 0.75
ECV = (0.5, 0.3, 0.2)

FROZEN_DIR = "configs/v0.6/frozen"
MANIFEST = os.path.join(FROZEN_DIR, "MANIFEST.sha256")


class IsolationError(RuntimeError):
    """Raised when a stage would touch seeds it must not see."""


def assert_seeds(seeds, allowed, stage):
    bad = sorted(set(seeds) - set(allowed))
    if bad:
        raise IsolationError(f"{stage} may only use seeds {min(allowed)}-{max(allowed)}; got {bad[:5]}...")


def base_config(d):
    return replace(load_config(BASE_CONFIG), link_setup_epochs=d, mutation_cap=None)


def cell_name(d, M):
    return f"d{d}_M{M}"


def frozen_path(arm, d=None, M=None):
    """Resolved at call time so tests can redirect FROZEN_DIR."""
    if arm == "A0":
        return os.path.join(FROZEN_DIR, "A0_static.yaml")
    return os.path.join(FROZEN_DIR, f"{arm}_{cell_name(d, M)}.yaml")


# ---------------------------------------------------------------- checksums
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def write_manifest(paths, manifest=None):
    manifest = manifest or MANIFEST
    lines = [f"{sha256(p)}  {os.path.relpath(p, os.path.dirname(manifest)).replace(os.sep, '/')}" for p in sorted(paths)]
    with open(manifest, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def verify_manifest(manifest=None):
    """Raise if the manifest is missing, a listed file is missing or changed, or an unlisted yaml was added."""
    manifest = manifest or MANIFEST
    if not os.path.exists(manifest):
        raise RuntimeError(f"manifest {manifest} not found: calibration has not been frozen")
    base = os.path.dirname(manifest)
    listed = {}
    with open(manifest, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                digest, rel = line.strip().split("  ", 1)
                listed[rel] = digest
    for rel, digest in listed.items():
        p = os.path.join(base, rel)
        if not os.path.exists(p):
            raise RuntimeError(f"frozen file missing: {p}")
        if sha256(p) != digest:
            raise RuntimeError(f"frozen file changed after freezing: {p}")
    extra = [f for f in os.listdir(base) if f.endswith((".yaml", ".csv")) and f not in listed]
    if extra:
        raise RuntimeError(f"unlisted files in {base}: {extra}")
    return listed


# ---------------------------------------------------------------- provenance
def git_state():
    def run(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    return {"commit": run("rev-parse", "HEAD"), "dirty_files": [l for l in run("status", "--porcelain").splitlines()
                                                                 if not l.startswith("??")]}


def versions():
    import numpy, pandas, scipy
    return {"python": sys.version.split()[0], "numpy": numpy.__version__, "scipy": scipy.__version__,
            "pandas": pandas.__version__}


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


# ---------------------------------------------------------------- parallel execution
def _task(args):
    cfg, seed, policy, want = args
    rows, _ = simulate(cfg, seed, policy, log_rounds=False)
    return rows if want == "rows" else rows[-1]["n_mutations"]


def run_tasks(tasks, workers):
    """tasks: list of (cfg, seed, policy, 'rows'|'count'). Order of results = order of tasks; deterministic."""
    if workers <= 1:
        return [_task(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_task, tasks, chunksize=4))
