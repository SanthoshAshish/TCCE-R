"""(3) Resilience Debt Estimator.  [PROPOSED mechanism]

Stress per epoch:   s_k = w_E * E_k + w_C * C_k + w_V * V_k        (each term in [0, 1])
Debt (CUSUM form):  D_k = max(0, D_{k-1} + s_k - kappa)

The accumulation rule is Page's one-sided CUSUM (Page 1954, established for change detection).
What is proposed here is (a) the choice of stress terms and weights and (b) using the CUSUM
statistic to drive topology mutation. As in standard CUSUM, D is reset after an alarm is acted on.
"""
import numpy as np


def volatility(changes_history, n_configured: int, window: int) -> float:
    """V in [0, 1]: environmental link state changes over the last `window` epochs / configured links.
    Our own mutations are deliberately excluded to avoid self-reinforcing triggering (risk R6)."""
    recent = sum(changes_history[-window:])
    return float(min(1.0, recent / max(1, n_configured)))


class CusumDebt:
    def __init__(self, cfg):
        self.w = np.array([cfg.w_E, cfg.w_C, cfg.w_V])
        self.kappa = cfg.kappa
        self.D = 0.0
        self.last_stress = 0.0

    def stress(self, E: float, C: float, V: float) -> float:
        return float(self.w @ np.array([E, C, V]))

    def update(self, E: float, C: float, V: float) -> float:
        self.last_stress = self.stress(E, C, V)
        self.D = max(0.0, self.D + self.last_stress - self.kappa)
        return self.D

    def repay(self) -> None:
        self.D = 0.0
