"""Simulation configuration. All parameters live here; YAML files override defaults."""
from dataclasses import dataclass, asdict, fields, replace
from typing import Optional

import os
import warnings

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

    # --- v0.6 options (read only by the v06_* policies; docs/PROTOCOL_v0.6.md) ---
    v06_threshold: Optional[float] = None  # calibrated h (A1, A2), Theta (A3, A4) or Theta0 (A5); None = never act
    v06_kappa: Optional[float] = None      # frozen CUSUM drift allowance: kappa_E (A3) or kappa_s (A4, A5)
    feedback_rule: str = "before_after"   # v0.7: "before_after" (legacy, v0.1-v0.6) or "counterfactual"
                                           #   (matched with/without-mutation replay; core/counterfactual.py)
    v06_count_pmf: Optional[str] = None    # rev. 4, A6/A7 only: "p0,p1,...,pM" = probabilities of an intended
                                           #   count of 0..M per seed; None = intended count is mutation_cap (rev. 3)

    # --- v0.8 options (revised study; all defaults reproduce v0.7 exactly) ---
    graph_family: str = "rgg"       # "rgg" | "er" (Erdos-Renyi) | "ba" (Barabasi-Albert scale-free)
    er_p_init: float = 0.12         # er: initial link probability (unused for ba; ba uses ba_m)
    er_p_pot: float = 0.20          # er/ba: probability that a non-initial pair is a candidate link
    ba_m: int = 2                   # ba: links per new node
    shock_epoch: int = -1           # abrupt topology change: one large correlated outage starting at this epoch
    shock_radius: float = 0.30
    shock_len: int = 15
    obs_noise: float = 0.0          # controller sees E, C, V corrupted by N(0, obs_noise^2) (clipped to [0, 1])
    obs_delay: int = 0              # controller sees E, C, V from this many epochs ago
    v08_w: Optional[str] = None     # "wE,wC,wV" override of the A4/A5/RCPR stress weights (sensitivity only)
    j_alpha: float = 1.0            # RCPR objective weights (docs/PROTOCOL_v0.8.md)
    j_beta: float = 0.5
    j_gamma: float = 0.05
    j_delta: float = 1.0
    risk_eps: float = 0.20          # empirical disconnection-risk tolerance of the RCPR constraint
    pred_horizon_extra: int = 3     # prediction horizon H = link_setup_epochs + pred_horizon_extra
    cand_k: int = 10                # candidates evaluated per decision epoch
    v08_front: int = 0              # hybrid H1: number F of front-loaded rewirings before risk-aware adaptation (0 = plain B8)
    rcpr_c_rewire: float = 0.25     # predictor: rewiring cost c0 (C(a) = c0 + c1 * [a releases a live link])
    rcpr_c_release: float = 0.75    # predictor: extra cost c1 of releasing a link that is currently working
    hz_window: int = 10             # hazard estimator: number of recent epochs used
    hz_prior_h: float = 0.02        # hazard estimator: prior per-epoch link failure probability
    hz_prior_r: float = 0.10        # hazard estimator: prior per-epoch repair probability
    hz_prior_w: float = 20.0        # hazard estimator: prior weight in pseudo link-epochs

    # --- Baselines ---
    reactive_threshold: float = 0.5
    period: int = 5
    mutation_cap: Optional[int] = None

    def __post_init__(self):
        """Reject mathematically invalid parameter combinations (v0.7). Every archived valid config passes."""
        errors = []
        if not (0.0 < self.eps < 1.0):
            errors.append(f"eps must be in (0, 1) (E uses ln e / ln eps); got {self.eps}")
        for name in ("w_E", "w_C", "w_V", "kappa"):
            if getattr(self, name) < 0:
                errors.append(f"{name} must be >= 0 (debt stress and CUSUM drift allowance); got {getattr(self, name)}")
        if self.feedback_horizon < 1:
            errors.append(f"feedback_horizon must be >= 1; got {self.feedback_horizon}")
        if self.vol_window < 1:
            errors.append(f"vol_window must be >= 1; got {self.vol_window}")
        if not (0 < self.theta_min <= self.theta0 <= self.theta_max):
            errors.append(f"need 0 < theta_min <= theta0 <= theta_max (otherwise the first clipped update can move "
                          f"theta the wrong way); got theta_min={self.theta_min}, theta0={self.theta0}, "
                          f"theta_max={self.theta_max}")
        if self.alpha < 0 or not (0 <= self.beta < 1):
            errors.append(f"need alpha >= 0 and 0 <= beta < 1 (theta must stay positive); got alpha={self.alpha}, "
                          f"beta={self.beta}")
        if self.feedback_rule not in ("before_after", "counterfactual"):
            errors.append(f"feedback_rule must be 'before_after' or 'counterfactual'; got {self.feedback_rule!r}")
        if self.rounds_per_epoch < 1 or self.epochs < 1:
            errors.append("epochs and rounds_per_epoch must be >= 1")
        # v0.8 options: reject invalid values only (defaults are unchanged and valid)
        if self.graph_family not in ("rgg", "er", "ba"):
            errors.append(f"graph_family must be 'rgg', 'er' or 'ba'; got {self.graph_family!r}")
        if self.graph_family == "er" and not (0.0 < self.er_p_init <= 1.0):
            errors.append(f"er_p_init must be in (0, 1] for graph_family='er'; got {self.er_p_init}")
        if self.graph_family != "rgg" and not (0.0 <= self.er_p_pot <= 1.0):
            errors.append(f"er_p_pot must be in [0, 1]; got {self.er_p_pot}")
        if self.graph_family == "ba" and not (1 <= self.ba_m < self.n_nodes):
            errors.append(f"ba_m must satisfy 1 <= ba_m < n_nodes; got {self.ba_m}")
        if self.obs_noise < 0 or self.obs_delay < 0 or int(self.obs_delay) != self.obs_delay:
            errors.append(f"obs_noise must be >= 0 and obs_delay a non-negative integer; got {self.obs_noise}, {self.obs_delay}")
        if self.shock_epoch >= 0 and (self.shock_radius <= 0 or self.shock_len < 1):
            errors.append("shock_radius must be > 0 and shock_len >= 1 when shock_epoch >= 0")
        if self.v08_w is not None:
            try:
                w = [float(x) for x in str(self.v08_w).split(",")]
                if len(w) != 3 or min(w) < 0 or sum(w) <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"v08_w must be 'wE,wC,wV' (three non-negative numbers, not all zero); got {self.v08_w!r}")
        if self.cand_k < 1 or self.pred_horizon_extra < 0 or self.v08_front < 0:
            errors.append("cand_k must be >= 1; pred_horizon_extra and v08_front must be >= 0")
        bad_hz = not (0 < self.hz_prior_h < 1 and 0 < self.hz_prior_r < 1)
        if min(self.rcpr_c_rewire, self.rcpr_c_release, self.hz_prior_w) < 0 or self.hz_window < 1 or bad_hz:
            errors.append("rcpr_c_* and hz_prior_w must be >= 0, hz_window >= 1, hz_prior_h and hz_prior_r in (0, 1)")
        if min(self.j_alpha, self.j_beta, self.j_gamma, self.j_delta, self.risk_eps) < 0:
            errors.append("j_alpha, j_beta, j_gamma, j_delta and risk_eps must be >= 0")
        if errors:
            raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))


def duplicate_top_level_keys(text: str):
    """Top-level keys that appear more than once in a YAML mapping (YAML silently keeps the last value)."""
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    if not isinstance(node, yaml.MappingNode):
        return []
    seen, dups = set(), []
    for key_node, _ in node.value:
        k = key_node.value
        if k in seen and k not in dups:
            dups.append(k)
        seen.add(k)
    return dups


def load_config(path: Optional[str] = None, **overrides) -> Config:
    data = {}
    if path:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        data = yaml.safe_load(text) or {}
        dups = duplicate_top_level_keys(text)
        if dups:
            warnings.warn(f"Config file {path} repeats key(s) {dups}; the LAST value of each is used",
                          UserWarning, stacklevel=2)
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
