"""(2) Distributed Consensus Monitor: turns a disagreement trajectory into epoch metrics."""
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ConsensusReport:
    final_error: float          # e(T)
    conv_round: Optional[int]   # first t with e(t) < eps, None if not reached in the epoch
    E_hat: float                # consensus stress in [0, 1]: 1 - min(1, ln e(T) / ln eps)
    rate: float                 # empirical per-round contraction (geometric mean of e(t+1)/e(t))


def summarize(err: np.ndarray, eps: float) -> ConsensusReport:
    """E_hat is the fraction of the required (log-scale) error decay NOT achieved this epoch:
    0 if e(T) <= eps, 1 if no progress. (conv_round/T was tried first but saturates at 1 whenever
    the epoch is too short to reach eps, which removes all signal.)"""
    T = len(err) - 1
    below = np.flatnonzero(err < eps)
    conv = int(below[0]) if len(below) else None
    progress = np.log(max(err[-1], 1e-300)) / np.log(eps)
    E_hat = float(1.0 - min(1.0, max(0.0, progress)))
    rate = float(max(err[-1], 1e-300) ** (1.0 / T))
    return ConsensusReport(float(err[-1]), conv, E_hat, rate)
