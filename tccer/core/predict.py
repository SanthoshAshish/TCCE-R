"""Predictive risk-constrained action evaluation (v0.8, docs/PROTOCOL_v0.8.md section 2).

For a candidate action a (rewire = remove one configured link, add one candidate link) or the null action:

  J(a) = alpha * E(a) + beta * R(a) + gamma * C(a) + delta * S(a)

  E(a): predicted consensus error over one epoch of T rounds on the *expected* post-action graph, in [0, 1]
        (same scale as the simulator's E_k). Each configured link gets a survival weight q_e (below); Metropolis weights
        are computed from expected degrees; rho = second-largest eigenvalue of the expected matrix W;
        E = 1 - clip(T * (-ln rho) / ln(1/eps), 0, 1).  Heuristic (Jensen gap ignored), validated empirically in the paper.
  R(a): disconnection-risk proxy in [0, 1]: min(1, (c - 1) * (1 - r)^H + sum over bridges b of (1 - (1 - h)^H)),
        with c the number of components of the post-action graph of currently-up links, h/r the online estimates of the
        per-epoch link failure/repair hazards (union bound over bridges).
  C(a): rewiring cost in {0, c0, c0 + c1}: 0 for the null action, c0 per rewire, plus c1 if a live link is released.
  S(a): link-setup penalty: max(0, E_interim(a) - E(null)) * d / H, where E_interim is E on the break-before-make graph.
  Uncertainty is not modelled, so there is no U term (it would be decorative).

q_e (survival of a configured link, averaged over the horizon): currently up -> (1 - h)^(H/2) * (1 - p_tr);
currently down -> (1 - (1 - r)^(H/2)) * (1 - p_tr); a link being set up counts as up once ready (it is ready by H).
Constraint (empirical, not a guarantee): R(a) <= max(risk_eps, R(null)).
"""
import math

import networkx as nx
import numpy as np


class HazardEstimator:
    """Online per-epoch failure/repair hazards of configured links from observed up/down transitions (window W)."""

    def __init__(self, window=10, prior_h=0.02, prior_r=0.1, prior_w=20.0):
        self.window, self.prior_h, self.prior_r, self.prior_w = window, prior_h, prior_r, prior_w
        self.hist = []              # (n_up_before, n_fail, n_down_before, n_repair)
        self.prev = None

    def update(self, state):
        down = state.down & state.configured
        if self.prev is not None:
            prev_down, cfg = self.prev
            both = cfg & state.configured
            up_b, dn_b = both & ~prev_down, both & prev_down
            self.hist.append((int(up_b.sum()), int((up_b & down).sum()), int(dn_b.sum()), int((dn_b & ~down).sum())))
            self.hist = self.hist[-self.window:]
        self.prev = (down.copy(), state.configured.copy())

    def rates(self):
        a = np.array(self.hist, dtype=float).sum(axis=0) if self.hist else np.zeros(4)
        h = (a[1] + self.prior_h * self.prior_w) / (a[0] + self.prior_w)
        r = (a[3] + self.prior_r * self.prior_w) / (a[2] + self.prior_w)
        return float(np.clip(h, 1e-4, 0.9)), float(np.clip(r, 1e-3, 0.99))


def _rho(n, u, v, q):
    """Second-largest eigenvalue of the expected Metropolis matrix for edges (u, v) with survival weights q."""
    if len(u) == 0:
        return 1.0
    d = np.bincount(u, weights=q, minlength=n) + np.bincount(v, weights=q, minlength=n)
    w = q / (1.0 + np.maximum(d[u], d[v]))
    W = np.zeros((n, n))
    np.add.at(W, (u, v), w)
    np.add.at(W, (v, u), w)
    W[np.diag_indices(n)] = 1.0 - W.sum(axis=1)
    vals = np.linalg.eigvalsh(W)
    return float(vals[-2])


class Predictor:
    def __init__(self, cfg, hazards):
        self.cfg, self.hz = cfg, hazards
        self.d = cfg.link_setup_epochs
        self.H = cfg.link_setup_epochs + cfg.pred_horizon_extra
        self.lneps = math.log(1.0 / cfg.eps)
        self.T = cfg.rounds_per_epoch

    def _E(self, state, cfg_mask, h, r, extra_up=None):
        """Predicted E on configured set cfg_mask. extra_up: edge index forced 'up' (a link that will be ready)."""
        up_p = (1 - h) ** (self.H / 2.0)
        rep_p = 1 - (1 - r) ** (self.H / 2.0)
        idx = np.flatnonzero(cfg_mask)
        q = np.where(state.down[idx], rep_p, up_p) * (1 - self.cfg.p_transient)
        if extra_up is not None:
            q[idx == extra_up] = up_p * (1 - self.cfg.p_transient)
        rho = _rho(state.n, state.eu[idx], state.ev[idx], q)
        if rho >= 1.0 - 1e-12:
            return 1.0
        return float(1.0 - min(1.0, max(0.0, self.T * (-math.log(max(rho, 1e-12))) / self.lneps)))

    def _R(self, state, cfg_mask, h, r, force_up=None):
        up = cfg_mask & (~state.down | (np.arange(state.P) == force_up if force_up is not None else False))
        g = nx.Graph()
        g.add_nodes_from(range(state.n))
        g.add_edges_from(zip(state.eu[up].tolist(), state.ev[up].tolist()))
        c = nx.number_connected_components(g)
        nb = sum(1 for _ in nx.bridges(g))
        p_b = 1.0 - (1.0 - h) ** self.H
        return float(min(1.0, (c - 1) * (1.0 - r) ** self.H + nb * p_b))

    def evaluate(self, state, mutation, live_mask):
        """Returns dict with E, R, C, S (and J pieces) for `mutation` (None = null action)."""
        h, r = self.hz.rates()
        cfg0 = state.configured
        if mutation is None:
            return {"E": self._E(state, cfg0, h, r), "R": self._R(state, cfg0, h, r), "C": 0.0, "S": 0.0}
        cfg1 = cfg0.copy()
        if mutation.add is not None:
            cfg1[mutation.add] = True
        if mutation.remove is not None:
            cfg1[mutation.remove] = False
        cfg_int = cfg0.copy()
        if mutation.remove is not None:
            cfg_int[mutation.remove] = False
        E1 = self._E(state, cfg1, h, r, extra_up=mutation.add)
        E_int = self._E(state, cfg_int, h, r)
        E0 = self._E(state, cfg0, h, r)
        released_live = mutation.remove is not None and bool(live_mask[mutation.remove])
        C = self.cfg.rcpr_c_rewire + (self.cfg.rcpr_c_release if released_live else 0.0)
        S = max(0.0, E_int - E0) * self.d / self.H
        return {"E": E1, "R": self._R(state, cfg1, h, r, force_up=mutation.add), "C": C, "S": S}

    def J(self, parts):
        c = self.cfg
        return c.j_alpha * parts["E"] + c.j_beta * parts["R"] + c.j_gamma * parts["C"] + c.j_delta * parts["S"]
