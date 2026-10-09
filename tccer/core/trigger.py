"""(4) Adaptive Mutation Trigger.  [PROPOSED mechanism]

Fire when D_k > theta_k and at least `trigger_cooldown` epochs have passed since the last mutation.
theta_k is supplied by AdaptiveThreshold (core/threshold.py).
"""


class Trigger:
    def __init__(self, cfg):
        self.cooldown = cfg.trigger_cooldown

    def should_fire(self, D: float, theta: float, k: int, last_mutation_epoch) -> bool:
        cooled = last_mutation_epoch is None or k - last_mutation_epoch >= self.cooldown
        return D > theta and cooled
