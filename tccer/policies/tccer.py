"""TCCE-R policy: wires components (3) debt, (4) trigger + threshold, (5)-(7) pipeline, (9) feedback."""
from tccer.core.debt import CusumDebt
from tccer.core.feedback import FeedbackEvaluator
from tccer.core.threshold import AdaptiveThreshold
from tccer.core.trigger import Trigger
from tccer.policies.base import Policy


class TCCERPolicy(Policy):
    name = "tccer"

    def __init__(self, cfg, pipeline, rng, adaptive_threshold: bool = True):
        super().__init__(cfg, pipeline, rng)
        self.debt = CusumDebt(cfg)
        self.threshold = AdaptiveThreshold(cfg)
        self.trigger = Trigger(cfg)
        self.feedback = FeedbackEvaluator(cfg)
        self.adaptive = adaptive_threshold
        self.E_hist = []
        self._fired = False
        self._feedback = ""

    def decide(self, k, obs, state):
        self.E_hist.append(obs["E_hat"])
        # (9) feedback on earlier mutations -> threshold update
        results = self.feedback.evaluate(k, self.E_hist)
        self._feedback = ";".join(f"{m}:{'S' if s else 'F'}" for m, s in results)
        if self.adaptive:
            for _, success in results:
                self.threshold.update(success)
        # (3) debt
        D = self.debt.update(obs["E_hat"], obs["C"], obs["V"])
        # (4) trigger
        self._fired = self.trigger.should_fire(D, self.threshold.theta, k, self.last_mutation_epoch)
        if not self._fired:
            return None
        # (5)-(7) evaluate, gate, select
        m = self._mutate(k, state)
        if m is not None:
            self.debt.repay()
            self.feedback.register(k)
        return m

    def info(self):
        return {"debt": self.debt.D, "stress": self.debt.last_stress, "theta": self.threshold.theta,
                "triggered": self._fired, "feedback": self._feedback}


class TCCERFixedThreshold(TCCERPolicy):
    """Ablation: theta never adapts."""
    name = "tccer_fixed"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng, adaptive_threshold=False)
