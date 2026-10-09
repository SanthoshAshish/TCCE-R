"""Failure processes (environment).

Common random numbers: every random draw is pre-generated per (epoch, round, potential edge)
from the seed alone, so every policy faces exactly the same failure trace.
  - transient: link i is unusable in round t with prob p_transient (Bernoulli, i.i.d.)
  - permanent: an up link fails with prob p_fail per epoch; a failed link is repaired with prob p_repair
"""
import numpy as np


class FailureTrace:
    def __init__(self, cfg, seed: int, n_potential: int):
        rng = np.random.default_rng([seed, 1])
        shape = (cfg.epochs, cfg.rounds_per_epoch, n_potential)
        self.u_transient = rng.random(shape, dtype=np.float32)
        self.u_fail = rng.random((cfg.epochs, n_potential), dtype=np.float32)
        self.u_repair = rng.random((cfg.epochs, n_potential), dtype=np.float32)
        self.p_transient, self.p_fail, self.p_repair = cfg.p_transient, cfg.p_fail, cfg.p_repair

    def epoch_update(self, k: int, down: np.ndarray) -> np.ndarray:
        new = down.copy()
        new[~down & (self.u_fail[k] < self.p_fail)] = True
        new[down & (self.u_repair[k] < self.p_repair)] = False
        return new

    def transient_up(self, k: int, t: int) -> np.ndarray:
        return self.u_transient[k, t] >= self.p_transient
