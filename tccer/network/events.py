"""Failure processes (environment).

Common random numbers: every random draw is pre-generated from the seed alone, so every policy faces
exactly the same failure trace.
  - transient: link i is unusable in round t with prob p_transient (Bernoulli, i.i.d.)
  - background: an up link fails with prob p_fail per epoch; a failed link is repaired with prob p_repair
    (two-state Markov on/off process per link)
  - bursts (v0.4, off unless burst_rate > 0): spatially correlated temporary outages. Each epoch a burst
    starts with prob burst_rate at a uniformly random centre; every potential link whose midpoint lies
    within burst_radius fails for L ~ U{burst_min_len..burst_max_len} epochs, then recovers.
    Geographically correlated failure models of this kind are standard in network-survivability studies;
    the specific parameters here are our choice.
A link is down if the background process OR any active burst says so.
"""
import numpy as np


class FailureTrace:
    def __init__(self, cfg, seed: int, n_potential: int, edge_mid=None):
        rng = np.random.default_rng([seed, 1])
        shape = (cfg.epochs, cfg.rounds_per_epoch, n_potential)
        self.u_transient = rng.random(shape, dtype=np.float32)
        self.u_fail = rng.random((cfg.epochs, n_potential), dtype=np.float32)
        self.u_repair = rng.random((cfg.epochs, n_potential), dtype=np.float32)
        self.p_transient, self.p_fail, self.p_repair = cfg.p_transient, cfg.p_fail, cfg.p_repair

        self.burst = np.zeros((cfg.epochs, n_potential), dtype=bool)
        self.bursts = []                          # (start_epoch, centre, length, n_links_hit)
        if cfg.burst_rate > 0:
            rng_b = np.random.default_rng([seed, 4])   # separate stream: does not perturb older draws
            for k in range(cfg.epochs):
                if rng_b.random() < cfg.burst_rate:
                    centre = rng_b.random(2)
                    L = int(rng_b.integers(cfg.burst_min_len, cfg.burst_max_len + 1))
                    hit = np.linalg.norm(edge_mid - centre, axis=1) <= cfg.burst_radius
                    self.burst[k:k + L, hit] = True
                    self.bursts.append((k, centre, L, int(hit.sum())))

    def epoch_update(self, k: int, down: np.ndarray) -> np.ndarray:
        """Background Markov process only (bursts are applied on top by the engine)."""
        new = down.copy()
        new[~down & (self.u_fail[k] < self.p_fail)] = True
        new[down & (self.u_repair[k] < self.p_repair)] = False
        return new

    def transient_up(self, k: int, t: int) -> np.ndarray:
        return self.u_transient[k, t] >= self.p_transient
