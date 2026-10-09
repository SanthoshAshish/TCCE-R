"""Simulation configuration. All parameters live here; YAML files override defaults."""
from dataclasses import dataclass, asdict, fields, replace
from typing import Optional

import os

import yaml


@dataclass(frozen=True)
class Config:
    # --- (1) Dynamic network state: random geometric graph in the unit square ---
    n_nodes: int = 40
    init_radius: float = 0.22       # initial links: node pairs closer than this
    radio_range: float = 0.32       # candidate links: node pairs closer than this (D8)

    # --- (2) Consensus: fresh x(0) each epoch (D1) ---
    epochs: int = 80
    rounds_per_epoch: int = 60
    eps: float = 1e-2               # convergence tolerance on normalized disagreement

    # --- Environment / failures (D10) ---
    p_transient: float = 0.05       # per-round, per-link outage probability
    p_fail: float = 0.01            # per-epoch probability an up link fails permanently
    p_repair: float = 0.10          # per-epoch probability a failed link is repaired

    # --- (3) Resilience debt, CUSUM form (D5) ---
    w_E: float = 0.5
    w_C: float = 0.3
    w_V: float = 0.2
    kappa: float = 0.30             # CUSUM drift allowance ("tolerable" stress per epoch)
    vol_window: int = 3

    # --- (4) Trigger + adaptive threshold (D6) ---
    theta0: float = 1.0
    theta_min: float = 0.25
    theta_max: float = 4.0
    alpha: float = 0.25             # theta *= (1 + alpha) after a failed mutation
    beta: float = 0.10              # theta *= (1 - beta)  after a successful mutation
    trigger_cooldown: int = 2       # min epochs between mutations
    feedback_horizon: int = 3       # epochs before/after used to judge a mutation

    # --- (5)/(7) Coupling evaluator + selector (D7, lexicographic) ---
    shortlist: int = 10
    gain_tolerance: float = 0.10    # candidates within 10% of best gain are "tied"

    # --- (6) Safety gate (D9) ---
    lambda2_min: float = 0.05
    d_max: int = 10
    edge_budget_frac: float = 1.15  # max live links = frac * initial links
    edge_cooldown: int = 5          # an edge just mutated cannot be touched for this many epochs
    budget_on: str = "live"         # "live" (v0.1/v0.2): failed links free budget; "configured": strict,
                                    #   failed links still occupy budget until the controller removes them
    link_setup_epochs: int = 0      # break-before-make cost: a removed link goes immediately, a new link
                                    #   becomes usable only this many epochs later (0 = v0.1/v0.2 behaviour)
    degree_fix: bool = False        # v0.3 fix: d_max applies only to the endpoints of the new link, and violating
                                    #   candidates are dropped before the gate (False = v0.1/v0.2 behaviour)

    # --- v0.4 options (all defaults reproduce v0.1-v0.3 exactly) ---
    degree_basis: str = "live"      # "configured": d_max counts failed and pending configured links too
                                    #   (ports stay occupied); "live" = v0.3 rule, which repairs can violate
    feedback_after_setup: bool = False  # True: feedback 'after' window starts when the new link is usable
    failed_link_value: str = "zero" # rewire removal value of a failed link: "zero" (v0.3: always the cheapest
                                    #   to release) or "if_up" (valued as if it were up; no free replacement)
    burst_rate: float = 0.0         # per-epoch probability that a spatial burst outage starts (0 = off)
    burst_radius: float = 0.15      # links whose midpoint lies within this distance of the burst centre fail
    burst_min_len: int = 2          # burst duration (epochs) ~ uniform integer in [min_len, max_len]
    burst_max_len: int = 6

    # --- v0.5 option ---
    scenario_file: Optional[str] = None  # YAML with custom nodes/links/initial values/failure events
                                    #   (see SIMULATOR_GUIDE.md); a relative path is resolved against the
                                    #   config file's folder. None = seed-generated network (v0.1-v0.4)

    # --- Baselines ---
    reactive_threshold: float = 0.5
    period: int = 5
    mutation_cap: Optional[int] = None


def load_config(path: Optional[str] = None, **overrides) -> Config:
    data = {}
    if path:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file {path} must contain 'key: value' lines")
    data.update({k: v for k, v in overrides.items() if v is not None})
    known = {f.name for f in fields(Config)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)} in {path or 'overrides'}. "
                         f"Check the spelling; valid keys are listed in tccer/config.py")
    sf = data.get("scenario_file")
    if sf and path and not os.path.isabs(sf):
        data["scenario_file"] = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), sf))
    return Config(**data)


def save_config(cfg: Config, path: str) -> None:
    with open(path, "w") as f:
        yaml.safe_dump(asdict(cfg), f, sort_keys=False)


__all__ = ["Config", "load_config", "save_config", "replace"]
