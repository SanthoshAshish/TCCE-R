"""Adaptive Debt Threshold Update.  [PROPOSED mechanism]

Multiplicative update, clipped to [theta_min, theta_max]:
  success -> theta *= (1 - beta)   (mutations are paying off: react earlier)
  failure -> theta *= (1 + alpha)  (mutations are not helping: be more conservative)
"""


class AdaptiveThreshold:
    def __init__(self, cfg):
        self.theta = cfg.theta0
        self.lo, self.hi = cfg.theta_min, cfg.theta_max
        self.alpha, self.beta = cfg.alpha, cfg.beta

    def update(self, success: bool) -> float:
        self.theta *= (1 - self.beta) if success else (1 + self.alpha)
        self.theta = min(self.hi, max(self.lo, self.theta))
        return self.theta
