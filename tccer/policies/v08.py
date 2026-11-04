"""v0.8 policies (docs/PROTOCOL_v0.8.md): component-ablation arms and the risk-constrained predictive rewiring
controller RCPR (the revised TCCE-R). All share the v0.6/v0.7 cooldown, per-run cap, one attempt per epoch, candidate
generator, safety gate and strict edge budget; only *when* and *which candidate* differ.

  B2/B3/B4  instantaneous stress thresholds (E+C, E+V, E+C+V), no accumulation, lexicographic selector
  B6        RCPR with a fixed trigger threshold (no adaptation, no feedback)
  B7        RCPR whose adaptation uses the legacy before/after feedback instead of counterfactual feedback
  B8        RCPR: CUSUM debt trigger + adaptive threshold with counterfactual feedback + predictive
            risk-constrained action selection (minimise J over the shortlist, act only if J(a*) < J(null) - b)
  P1        RCPR-NoDebt: the predictive decision rule evaluated every epoch, no debt, no adaptation
  H1        hybrid: F front-loaded rewirings (cfg.v08_front), then B8 (see HybridArm)
"""
import math

from tccer.config import replace
from tccer.core.feedback import FeedbackEvaluator
from tccer.core.predict import HazardEstimator, Predictor
from tccer.core.selector import EMPTY_SELECTION
from tccer.policies.v06 import HORIZON, CusumEArm, CusumECVArm, TCCERArm, ThresholdArm, V06Policy

WEIGHTS = {"B2": (0.5, 0.3, 0.0), "B3": (0.5, 0.0, 0.2), "B4": (0.5, 0.3, 0.2)}


class InstantStressArm(ThresholdArm):
    """B2-B4: attempt when the instantaneous stress s_k = (wE E + wC C + wV V) / (wE + wC + wV) exceeds h."""
    name = "v08_instant"
    key = "B4"

    def update_statistic(self, k, obs):
        wE, wC, wV = WEIGHTS[self.key]
        self.stat = (wE * obs["E_hat"] + wC * obs["C"] + wV * obs["V"]) / (wE + wC + wV)


class InstantB2(InstantStressArm):
    name, key = "v08_b2", "B2"


class InstantB3(InstantStressArm):
    name, key = "v08_b3", "B3"


class InstantB4(InstantStressArm):
    name, key = "v08_b4", "B4"


class PredictiveMixin:
    """Candidate-action evaluation: the shared generator + gate give a feasible shortlist; J picks among them."""

    def _init_pred(self, cfg):
        self.hz = HazardEstimator(cfg.hz_window, cfg.hz_prior_h, cfg.hz_prior_r, cfg.hz_prior_w)
        self.pred = Predictor(cfg, self.hz)
        self.n_eval = self.n_deferred = self.n_risk_filtered = self.n_pred_attempts = 0
        self.last_benefit = float("nan")
        self.last_J = (float("nan"), float("nan"))

    def min_benefit(self):
        return 0.0

    def _predictive_select(self, k, state):
        pipe, cfg = self.pipeline, self.cfg
        order, tabu = pipe._ranked(state, k, "lexicographic", None)
        pipe.last = dict(EMPTY_SELECTION, n_candidates=len(order),
                         select_outcome="no_candidates" if not order else "all_rejected")
        feas = []
        for m, _ in order[:30]:
            if pipe.gate.check(state, m, tabu)[0]:
                feas.append(m)
                if len(feas) >= cfg.cand_k:
                    break
        self.n_pred_attempts += 1
        if not feas:
            return None
        live = state.live_mask()
        null = self.pred.evaluate(state, None, live)
        J0 = self.pred.J(null)
        best, bestJ = None, math.inf
        for m in feas:
            parts = self.pred.evaluate(state, m, live)
            self.n_eval += 1
            if parts["R"] > max(cfg.risk_eps, null["R"]) + 1e-12:      # empirical risk constraint
                self.n_risk_filtered += 1
                continue
            J = self.pred.J(parts)
            if J < bestJ:
                best, bestJ = m, J
        self.last_J = (J0, bestJ if best is not None else float("nan"))
        self.last_benefit = J0 - bestJ if best is not None else float("nan")
        if best is None or J0 - bestJ <= self.min_benefit():
            self.n_deferred += 1
            pipe.last["select_outcome"] = "deferred"
            return None
        pipe.last.update(select_outcome="mutated",
                         removed_failed_link=bool(best.remove is not None and not live[best.remove]))
        return best

    def pred_info(self):
        return {"rcpr_evals": self.n_eval, "rcpr_deferred": self.n_deferred, "rcpr_risk_filtered": self.n_risk_filtered,
                "rcpr_J_null": self.last_J[0], "rcpr_J_best": self.last_J[1], "rcpr_benefit": self.last_benefit}


class RCPRArm(PredictiveMixin, TCCERArm):
    """B8: debt trigger (adaptive threshold, counterfactual feedback) + predictive risk-constrained selection."""
    name = "v08_rcpr"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self._init_pred(cfg)

    def decide(self, k, obs, state):
        self.hz.update(state)
        return super().decide(k, obs, state)

    def _select(self, k, state):
        return self._predictive_select(k, state)

    def info(self):
        return {**super().info(), **self.pred_info()}


class RCPRFixedArm(RCPRArm):
    """B6: as B8 with the trigger threshold fixed (no adaptation, no feedback)."""
    name = "v08_rcpr_fixed"

    def update_statistic(self, k, obs):
        CusumECVArm.update_statistic(self, k, obs)

    def _attempt(self, k, state):
        return V06Policy._attempt(self, k, state)

    def on_success(self, k):
        CusumEArm.on_success(self, k)

    def info(self):
        return {**CusumEArm.info(self), **self.pred_info(), "theta": self.theta}


class RCPRLegacyArm(RCPRArm):
    """B7: as B8 but the threshold adapts from the legacy before/after feedback. The arm itself selects the legacy rule,
    whatever cfg.feedback_rule says, so B7 differs from B8 by construction and cannot silently become B8."""
    name = "v08_rcpr_legacy"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self._cf = False
        self.feedback = FeedbackEvaluator(replace(cfg, feedback_horizon=HORIZON, feedback_after_setup=True))


class RCPRNoDebtArm(PredictiveMixin, V06Policy):
    """P1: predictive rule evaluated at every eligible epoch; acts only if predicted net benefit > b (= cfg.v06_threshold)."""
    name = "v08_pred_only"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self._init_pred(cfg)

    def min_benefit(self):
        return self.cfg.v06_threshold

    def decide(self, k, obs, state):
        self.hz.update(state)
        return super().decide(k, obs, state)

    def update_statistic(self, k, obs):
        self.stat = obs["E_hat"]

    def wants_attempt(self, k):
        return self.cfg.v06_threshold is not None

    def _select(self, k, state):
        return self._predictive_select(k, state)

    def info(self):
        return {**super().info(), **self.pred_info()}


class HybridArm(RCPRArm):
    """H1 Hybrid-FrontRisk (docs/PROTOCOL_v0.8.md section 7). F = cfg.v08_front.

    Phase 1 (front-loaded): while fewer than F phase-1 rewirings are done and k < 4F, the only attempts are the owed
    front-loaded ones: an attempt is owed from epoch 2*n_front on, selected state-blind by the shared lexicographic
    selector (exactly as A7). Phase-1 mutations count against the cap M, but do NOT reset the debt and are NOT
    registered for threshold feedback (they are not decisions of the adaptive rule). The debt statistic keeps
    accumulating during phase 1.
    Phase 2 (risk-aware): afterwards the arm is exactly B8 (debt trigger, adaptive threshold with counterfactual
    feedback, predictive risk-constrained selection) for the remaining budget.
    F = 0 gives B8 exactly.
    """
    name = "v08_hybrid"

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.n_front = 0
        self._in_front = False

    def _phase1(self, k):
        F = self.cfg.v08_front
        return self.n_front < F and k < 4 * F

    def wants_attempt(self, k):
        if self._phase1(k):
            return k >= 2 * self.n_front
        return super().wants_attempt(k)

    def _attempt(self, k, state):
        if not self._phase1(k):
            return super()._attempt(k, state)
        self._in_front = True
        try:
            m = V06Policy._attempt(self, k, state)         # no snapshot/feedback registration for phase-1 moves
        finally:
            self._in_front = False
        if m is not None:
            self.n_front += 1
        return m

    def on_success(self, k):
        if not self._in_front:                              # phase-1 moves neither reset the debt nor feed back
            super().on_success(k)

    def _select(self, k, state):
        if self._in_front:
            return self.pipeline.select(state, k, mode="lexicographic", rng=self.rng)
        return self._predictive_select(k, state)

    def info(self):
        return {**super().info(), "hyb_n_front": self.n_front}


V08_ARMS = {"B2": InstantB2, "B3": InstantB3, "B4": InstantB4, "B6": RCPRFixedArm, "B7": RCPRLegacyArm,
            "B8": RCPRArm, "P1": RCPRNoDebtArm, "H1": HybridArm}
