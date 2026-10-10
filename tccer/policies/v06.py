"""v0.6 trigger-comparison arms A1-A7 (docs/PROTOCOL_v0.6.md, sections 2.1-2.3). A0 is the existing `static`.

Every arm follows the same order at the end of epoch k (protocol 2.1):
  1. update the arm's statistic (A5: apply feedback first);
  2. stop if realised == M (cap = cfg.mutation_cap; None = uncapped, used only for calibration);
  3. no attempt unless k - last_success >= COOLDOWN;
  4. one attempt if the arm's condition holds.
An attempt calls the shared MutationPipeline.select (same selector, gate, budget). A failed attempt changes nothing.
Constants below are frozen by the protocol and deliberately not configurable.
"""
import numpy as np

from tccer.config import replace
from tccer.core.feedback import FeedbackEvaluator
from tccer.policies.base import Policy

COOLDOWN = 2                     # protocol 2.1 (equals trigger_cooldown of v0.4 configs)
WINDOW = 4                       # A2 moving-average window
ECV_WEIGHTS = (0.5, 0.3, 0.2)    # A4/A5 stress s = 0.5E + 0.3C + 0.2V
THETA_LO, THETA_HI = 0.25, 4.0   # A5 bounds = [THETA_LO * Theta0, THETA_HI * Theta0]
ALPHA, BETA, HORIZON = 0.25, 0.10, 3


class V06Policy(Policy):
    """Shared attempt mechanics, cap, cooldown and logging for A1-A7."""
    name = "v06_base"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.last_success = None
        self.attempts = 0
        self.failed_attempts = 0
        self.stat = float("nan")
        self._attempted = False
        self._attempt_ok = False

    # -- protocol 2.1, steps 2-4 ------------------------------------------------------------
    def _cap_reached(self):
        cap = self.cfg.mutation_cap
        return cap is not None and self.n_mutations >= cap

    def _cooled(self, k):
        return self.last_success is None or k - self.last_success >= COOLDOWN

    def _attempt(self, k, state):
        self._attempted = True
        self.attempts += 1
        m = self.pipeline.select(state, k, mode="lexicographic", rng=self.rng)
        if m is None:
            self.failed_attempts += 1
            return None
        self.n_mutations += 1
        self.last_success = k
        self.last_mutation_epoch = k
        self._attempt_ok = True
        self.on_success(k)
        return m

    def on_success(self, k):
        pass

    def update_statistic(self, k, obs):
        raise NotImplementedError

    def wants_attempt(self, k):
        raise NotImplementedError

    def decide(self, k, obs, state):
        self._attempted = self._attempt_ok = False
        self.update_statistic(k, obs)                    # step 1
        if self._cap_reached():                          # step 2
            return None
        if not self._cooled(k):                          # step 3
            return None
        if self.wants_attempt(k):                        # step 4
            return self._attempt(k, state)
        return None

    def info(self):
        return {"v06_stat": self.stat, "v06_attempt": self._attempted, "v06_attempt_ok": self._attempt_ok,
                "v06_attempts_total": self.attempts, "v06_failed_attempts_total": self.failed_attempts}


class ThresholdArm(V06Policy):
    """Attempt when the statistic exceeds the calibrated threshold (cfg.v06_threshold)."""

    def wants_attempt(self, k):
        h = self.cfg.v06_threshold
        return h is not None and self.stat > h


class ReactiveArm(ThresholdArm):
    """A1: S_k = E_k."""
    name = "v06_reactive"

    def update_statistic(self, k, obs):
        self.stat = obs["E_hat"]


class MovingAverageArm(ThresholdArm):
    """A2: S_k = mean(E_j, j = max(0, k-3)..k); sliding window, never reset."""
    name = "v06_movavg"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.hist = []

    def update_statistic(self, k, obs):
        self.hist.append(obs["E_hat"])
        self.stat = float(np.mean(self.hist[-WINDOW:]))


class MovingAverageResetArm(MovingAverageArm):
    """A2-reset (sensitivity C-4, tuning seeds only): as A2, but the window is cleared after a successful mutation."""
    name = "v06_movavg_reset"

    def update_statistic(self, k, obs):
        self.hist.append(obs["E_hat"])
        self.stat = float(np.mean(self.hist[-WINDOW:]))

    def on_success(self, k):
        self.hist = []


class CusumEArm(ThresholdArm):
    """A3: D_k = max(0, D_{k-1} + E_k - kappa_E); D <- 0 after a successful mutation only."""
    name = "v06_cusum_e"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.stat = 0.0

    def stress(self, obs):
        return obs["E_hat"]

    def update_statistic(self, k, obs):
        kappa = self.cfg.v06_kappa if self.cfg.v06_kappa is not None else float("inf")
        self.stat = max(0.0, self.stat + self.stress(obs) - kappa)

    def on_success(self, k):
        self.stat = 0.0

    def info(self):
        return {**super().info(), "debt": self.stat}


class CusumECVArm(CusumEArm):
    """A4: as A3 with s = 0.5E + 0.3C + 0.2V and kappa_s; fixed Theta."""
    name = "v06_cusum_ecv"

    def stress(self, obs):
        wE, wC, wV = ECV_WEIGHTS
        return wE * obs["E_hat"] + wC * obs["C"] + wV * obs["V"]


class TCCERArm(CusumECVArm):
    """A5: A4 with adaptive Theta in [Theta0/4, 4*Theta0]; feedback windows per protocol 2.2."""
    name = "v06_tccer"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.theta0 = cfg.v06_threshold
        self.theta = self.theta0
        # protocol 2.2: after-window m+1+d..m+d+3, before-window m-2..m, regardless of the base config's settings
        self.feedback = FeedbackEvaluator(replace(cfg, feedback_horizon=HORIZON, feedback_after_setup=True))
        self.E_hist = []
        self.n_updates = self.n_success = self.n_failure = 0
        self._update = ""

    def update_statistic(self, k, obs):
        self.E_hist.append(obs["E_hat"])
        self._update = ""
        if self.theta is not None:
            for m, ok in self.feedback.evaluate(k, self.E_hist):
                self.n_updates += 1
                if ok:
                    self.n_success += 1
                    self.theta = max(THETA_LO * self.theta0, self.theta * (1 - BETA))
                else:
                    self.n_failure += 1
                    self.theta = min(THETA_HI * self.theta0, self.theta * (1 + ALPHA))
                self._update += f"{m}:{'S' if ok else 'F'};"
        super().update_statistic(k, obs)

    def wants_attempt(self, k):
        return self.theta is not None and self.stat > self.theta

    def on_success(self, k):
        super().on_success(k)
        self.feedback.register(k)

    def info(self):
        return {**super().info(), "theta": self.theta, "theta_update": self._update,
                "theta_updates_total": self.n_updates, "theta_success_total": self.n_success,
                "theta_failure_total": self.n_failure, "feedback_pending": len(self.feedback.pending)}


class ScheduledArm(V06Policy):
    """A6/A7: attempts owed by a fixed schedule, tracked by the backlog counter P (protocol 2.3)."""

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        M = cfg.mutation_cap or 0
        self.schedule = self.make_schedule(M, cfg.epochs)
        self._sched_set = set(self.schedule)
        self.backlog = 0
        self.realised_epochs = []

    def make_schedule(self, M, epochs):
        raise NotImplementedError

    def update_statistic(self, k, obs):
        if k in self._sched_set:
            self.backlog += 1
        self.stat = float(self.backlog)

    def wants_attempt(self, k):
        return self.backlog > 0

    def on_success(self, k):
        self.backlog -= 1
        self.realised_epochs.append(k)

    def lags(self):
        return [r - s for r, s in zip(self.realised_epochs, self.schedule)]

    def info(self):
        return {**super().info(), "v06_backlog": self.backlog, "v06_schedule": " ".join(map(str, self.schedule))}


class RandomTimingArm(ScheduledArm):
    """A6: M distinct epochs drawn uniformly from {0..epochs-1} with stream [seed,3]; redraw until all gaps >= 2."""
    name = "v06_random"

    def make_schedule(self, M, epochs):
        if M <= 0:
            return []
        if 2 * (M - 1) >= epochs:
            raise ValueError(f"cannot place {M} attempts with gaps >= {COOLDOWN} in {epochs} epochs")
        while True:
            s = sorted(int(x) for x in self.rng.choice(epochs, size=M, replace=False))
            if all(b - a >= COOLDOWN for a, b in zip(s, s[1:])):
                return s


class FrontLoadedArm(ScheduledArm):
    """A7: epochs 0, 2, 4, ..., 2(M-1)."""
    name = "v06_front"

    def make_schedule(self, M, epochs):
        return [COOLDOWN * j for j in range(M) if COOLDOWN * j < epochs]


V06_ARMS = {"A1": ReactiveArm, "A2": MovingAverageArm, "A3": CusumEArm, "A4": CusumECVArm, "A5": TCCERArm,
            "A6": RandomTimingArm, "A7": FrontLoadedArm, "A2r": MovingAverageResetArm}
