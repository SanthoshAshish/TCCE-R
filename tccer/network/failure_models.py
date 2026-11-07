"""Extended failure models (Revision 2 / COCRO evaluation). Additive: with failure_model = "legacy" (the default) make_trace returns the original
FailureTrace and nothing changes. All randomness is pre-generated from the seed and the processes depend only on the (policy-independent) background
state, so every policy faces exactly the same failure trace (common random numbers), as in the original model.

failure_model = "extended" applies whichever of the following are switched on (neutral parameters switch them off):
  * cascade  (casc_gain > 1): an up link that shares a node with a link that was down in the previous epoch fails with hazard min(0.9, p_fail * casc_gain)
             (failure-induced failures; a stylised contagion model, our choice);
  * node     (node_rate > 0): each node fails per epoch with probability node_rate and is repaired with probability node_repair (independent two-state
             process from its own stream [seed, 8]); while a node is down every potential link incident to it is down (written into the burst mask);
  * regime   (regime_epoch >= 0): from that epoch the link failure probability is multiplied by regime_mult (an abrupt, unannounced change of conditions).
Spatial bursts and the shock option of the original model remain available alongside. Mobility-driven topology change is NOT modelled.
"""
import numpy as np

from tccer.network.events import FailureTrace


class ExtendedTrace(FailureTrace):
    def __init__(self, cfg, seed, n_potential, edge_mid, eu, ev, n):
        super().__init__(cfg, seed, n_potential, edge_mid=edge_mid)
        self.cfg_x, self.eu, self.ev, self.n = cfg, np.asarray(eu), np.asarray(ev), n
        self.node_down = np.zeros((cfg.epochs, n), dtype=bool)
        if cfg.node_rate > 0:
            rng = np.random.default_rng([seed, 8])               # own stream: the original draws are untouched
            down = np.zeros(n, dtype=bool)
            for k in range(cfg.epochs):
                u_fail, u_rep = rng.random(n), rng.random(n)
                down = np.where(down, u_rep >= cfg.node_repair, u_fail < cfg.node_rate)
                self.node_down[k] = down
                if down.any():
                    self.burst[k] |= down[self.eu] | down[self.ev]

    def epoch_update(self, k, down):
        c = self.cfg_x
        h = self.p_fail * (c.regime_mult if 0 <= c.regime_epoch <= k else 1.0)
        hz = np.full(len(down), h)
        if c.casc_gain > 1.0:
            dn = np.bincount(self.eu, weights=down.astype(float), minlength=self.n) + np.bincount(self.ev, weights=down.astype(float), minlength=self.n)
            hz = np.where((dn[self.eu] + dn[self.ev]) > 0, min(0.9, h * c.casc_gain), h)
        new = down.copy()
        new[~down & (self.u_fail[k] < hz)] = True
        new[down & (self.u_repair[k] < self.p_repair)] = False
        return new


def make_trace(cfg, seed, n_potential, edge_mid, eu, ev, n):
    """The original FailureTrace unless cfg.failure_model == 'extended'."""
    if cfg.failure_model == "legacy":
        return FailureTrace(cfg, seed, n_potential, edge_mid=edge_mid)
    return ExtendedTrace(cfg, seed, n_potential, edge_mid, eu, ev, n)
