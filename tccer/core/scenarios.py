"""COCRO v2: posterior-sampled future failure scenarios (CFPE sampler) with common random numbers across candidate actions.
[PROPOSED; docs/COCRO_DESIGN.md 2.2, 2.6, 2.7]

A scenario set holds, for S draws, the effective down mask of EVERY potential link for the next H epochs (k+1 .. k+H):
  * each scenario draws its own parameter vector theta_s from the CFPE posterior (Thompson-style) unless plug_in=True (posterior mean for all);
  * links currently down: the downtime component (short/long) is drawn from its posterior given the link's age; repair per epoch with the
    component's rate; up links fail with the lagged-adjacency hazard h[N] where N = number of adjacent links down in the PREVIOUS (simulated) epoch;
    new episodes draw a component from the mixture weight; links attributed to a down node are held down by the node process;
  * nodes: a flagged node repairs with node_r per epoch; an unflagged node fails with node_h per epoch (all incident links then down).
The same ScenarioSet object is used for the null action and for every candidate (common random numbers).
Independence from the environment (leakage guard): controller streams come from controller_rng(seed, epoch, role), whose SeedSequence key contains
the marker CONTROLLER_STREAM, so it can never coincide with the environment's streams [seed, 0..6]; the sampler never touches FailureTrace.
Not modelled (stated): spatial common-cause bursts, regime changes within the horizon, mobility.
"""
from dataclasses import dataclass

import numpy as np
from scipy import sparse

from tccer.core.failure_model import PropagationFailureModel

CONTROLLER_STREAM = 7919            # marker; environment streams use [seed, 0..6]


def controller_rng(seed: int, epoch: int, role: int):
    """Controller-owned random stream. role distinguishes independent uses, e.g. 1 = selection scenarios, 2 = test scenarios (cross-fitting)."""
    return np.random.default_rng([seed, CONTROLLER_STREAM, epoch, role])


@dataclass
class ScenarioSet:
    down: np.ndarray                 # (S, H, P) bool, effective link down masks for epochs k+1 .. k+H
    node_down: np.ndarray            # (S, H, n) bool
    k: int                           # decision epoch
    thetas: list                     # the S parameter draws (for diagnostics)

    @property
    def S(self):
        return self.down.shape[0]

    @property
    def H(self):
        return self.down.shape[1]


class ScenarioSampler:
    def __init__(self, model: PropagationFailureModel):
        self.m = model
        n, P = model.n, model.P
        B = sparse.csr_matrix((np.ones(2 * P, dtype=np.float32), (np.r_[np.arange(P), np.arange(P)], np.r_[model.eu, model.ev])), shape=(P, n))
        self.BT = B.T.tocsr()                                              # node x link incidence

    def sample(self, S, H, rng, plug_in=False) -> ScenarioSet:
        m, P, n, nb = self.m, self.m.P, self.m.n, self.m.prm.nb
        thetas = [m.map_theta()] * S if plug_in else [m.sample_theta(rng) for _ in range(S)]
        h = np.stack([t.h for t in thetas])                                   # (S, nb)
        w = np.array([t.w for t in thetas])
        r_s, r_l = np.array([t.r_s for t in thetas]), np.array([t.r_l for t in thetas])
        node_h, node_r = np.array([t.node_h for t in thetas]), np.array([t.node_r for t in thetas])
        prev = m.prev_down if m.prev_down is not None else np.zeros(P, bool)
        base = np.tile(prev & ~m.ep_excluded, (S, 1))                         # link-level (own-process) down state
        node = np.tile(m.node_down, (S, 1))
        # downtime component of each currently-down link, drawn from its posterior given its age
        a = m.age[None, :].astype(float)
        ws, wl = (1 - w)[:, None] * (1 - r_s)[:, None] ** a, w[:, None] * (1 - r_l)[:, None] ** a
        long_ = rng.random((S, P)) < wl / np.maximum(ws + wl, 1e-300)
        out = np.zeros((S, H, P), dtype=bool)
        nout = np.zeros((S, H, n), dtype=bool)
        eff_prev = base | (node[:, m.eu] | node[:, m.ev])
        for j in range(H):
            dn = np.asarray(self.BT @ eff_prev.T.astype(np.float32)).T            # (S, n): adjacent links down at each node in the previous epoch
            N =np.minimum((dn[:, m.eu] + dn[:, m.ev]).astype(int), nb - 1)
            hz = np.take_along_axis(h, N, axis=1)
            u_f, u_r = rng.random((S, P)), rng.random((S, P))
            fail = ~eff_prev & (u_f < hz)
            rate = np.where(long_, r_l[:, None], r_s[:, None])
            repair = base & (u_r < rate)
            newly = fail & ~base
            long_ = np.where(newly, rng.random((S, P)) < w[:, None], long_)
            base = (base & ~repair) | fail
            u_n = rng.random((S, n))
            node = np.where(node, u_n >= node_r[:, None], u_n < node_h[:, None])
            eff = base | (node[:, m.eu] | node[:, m.ev])
            out[:, j], nout[:, j], eff_prev = eff, node, eff
        return ScenarioSet(out, nout, m.k, thetas)
