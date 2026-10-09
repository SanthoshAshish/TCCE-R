"""Baselines. All share TCCE-R's candidate set, safety gate, edge budget and (via mutation_cap) budget."""
from tccer.policies.base import Policy


class StaticPolicy(Policy):
    """B0: never mutate."""
    name = "static"

    def decide(self, k, obs, state):
        return None


class RandomPolicy(Policy):
    """B1: every `period` epochs apply a random gate-approved mutation."""
    name = "random"

    def decide(self, k, obs, state):
        if k > 0 and k % self.cfg.period == 0:
            return self._mutate(k, state, mode="random")
        return None


class PeriodicGreedyPolicy(Policy):
    """B2: every `period` epochs apply the lexicographic-best mutation (no debt, no trigger)."""
    name = "periodic"

    def decide(self, k, obs, state):
        if k > 0 and k % self.cfg.period == 0:
            return self._mutate(k, state)
        return None


class ReactivePolicy(Policy):
    """B3: mutate when this epoch's consensus stress exceeds a fixed threshold (no accumulation)."""
    name = "reactive"

    def decide(self, k, obs, state):
        cooled = self.last_mutation_epoch is None or k - self.last_mutation_epoch >= self.cfg.trigger_cooldown
        if obs["E_hat"] > self.cfg.reactive_threshold and cooled:
            return self._mutate(k, state)
        return None
