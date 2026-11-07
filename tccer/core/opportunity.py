"""COCRO v2, component MOCO: shadow price of one mutation unit by Monte-Carlo policy rollout. [PROPOSED; docs/COCRO_DESIGN.md 2.4; validated in the
toy study docs/COCRO_TOY_STUDY.md (an exogenous toy chain with a known model; NOT validated in the simulator)]

For a chosen candidate a* at decision epoch k with m units left, on S posterior scenarios (failure paths to the END of the run), compare
  W_act  : total gain of "act now with a*, then follow the base policy pi0 with m-1 units"   (pi0 first slot at k+2: cooldown)
  W_wait : total gain of "do nothing now, follow pi0 with m units"                           (pi0 first slot at k+1)
  G_now  : total gain of a* alone (never act again)
where a path's gain is sum_t w_t [ E^(null_t) - E^(branch_t) ] over a strided set of epochs t (stride = base-policy slot spacing; w_t = epochs
represented), E^ is the GainEstimator's surrogate error on the scenario's live graph, 'null' = never act from now.
  shadow price      Lambda = E[W_wait] - ( E[W_act] - E[G_now] )       (value of keeping the unit net of what acting later would add)
  net gain          N = E[G_now] - c_op
  decision          act iff N > Lambda  <=>  E[W_act] - c_op > E[W_wait]    (one-step policy improvement over pi0; ties -> wait)
Base policy pi0 (non-anticipative: it sees only the scenario graph at its own decision epoch, never the scenario's future): at each slot, take
the single best action (merge components, then largest first-order lambda2 gain minus the cheapest removal's loss), and act iff its estimated net
reward R = d*(E_c - E_interim) + (E_c - E_final)*max(0, tau_t - d) exceeds c_op, with E_c/E_interim/E_final the surrogate error of the current
live graph, of the graph with the removal, and of the graph after the rewire (the same structure as the toy greedy rule 'act iff R > 0': the setup
loss is its natural hurdle). Budget, cooldown and edge tabu are respected.
Approximations (stated): the path is evaluated densely for the setup window and first slot (d + 3 epochs) and then every `slot` epochs with a stratified phase (s mod slot), an unbiased systematic sample over scenarios; pi0 evaluated at slot epochs only; removal valuation as in the
existing generator (failed_link_value); persistence is not used inside pi0.
"""
import math
from dataclasses import dataclass

import numpy as np

from tccer.core.cocro_ops import Rules, candidate_pairs


@dataclass(frozen=True)
class RolloutParams:
    slot: int = 4              # base-policy slot spacing = path-evaluation stride (epochs)
    c_op: float = 0.0          # operational price of a reconfiguration, error-epochs (primary analysis: 0)


@dataclass
class RolloutResult:
    W_wait: float
    W_act: float
    G_now: float
    N: float
    Lambda: float
    advantage: float           # E[W_act] - c_op - E[W_wait]
    se: float                  # standard error of the paired advantage over scenarios
    act: bool
    S: int


@dataclass
class ReserveResult:
    """Fix 2 (budget reservation) result. *0 fields are the original one-step rollout quantities (hurdle 0) on the test scenarios."""
    N: float
    Lambda: float
    advantage0: float          # E_test[W_act(0)] - c_op - E_test[W_wait(0)]  (equals RolloutPricer.price().advantage for the same scenarios)
    se0: float
    W_wait0: float
    W_act0: float
    advantage: float           # with the hurdles chosen on the independent selection scenarios: E_test[W_act(h_a)] - c_op - E_test[W_wait(h_w)]
    f_wait: float              # chosen hurdle factors (multiples of the scale); 0 = no reservation
    f_act: float
    scale: float               # hurdle scale: the base policy's own net-reward statistic R* for a* in the current state (same units as the hurdle)
    act: bool                  # advantage0 > 0 AND advantage > 0 (never more eager than the one-step rule)
    checked: bool              # False if the one-step rule already said wait (hurdles not evaluated)


class RolloutPricer:
    def __init__(self, n, eu, ev, length, estimator, rules: Rules, d, edge_cooldown, budget, T_total, params: RolloutParams = RolloutParams()):
        self.n, self.eu, self.ev, self.length, self.ge = n, np.asarray(eu), np.asarray(ev), np.asarray(length), estimator
        self.rules, self.d, self.cool, self.budget, self.T, self.prm = rules, d, edge_cooldown, budget, T_total, params

    # -------------------------------------------------------------- helpers
    def _live(self, conf, ready, down_t, t):
        return conf & ~down_t & (ready <= t)

    def _apply(self, conf, ready, touched, mut, t):
        conf, ready, touched = conf.copy(), ready.copy(), touched.copy()
        if mut[1] is not None:
            conf[mut[1]] = False
            touched[mut[1]] = t
        if mut[0] is not None:
            conf[mut[0]] = True
            ready[mut[0]] = t + 1 + self.d
            touched[mut[0]] = t
        return conf, ready, touched

    def _path(self, conf, ready, touched, m, down, k, eval_set, slot_set, first_slot, cache, act_policy, hurdle=0.0):
        """Surrogate error at the evaluation epochs along one branch (time-ordered). If act_policy, the base policy pi0 decides at the slot
        epochs >= first_slot (its action takes effect from the next epoch). Returns {epoch: E}."""
        out = {}
        for t in sorted(eval_set | (slot_set if act_policy else set())):
            live = self._live(conf, ready, down[t - k - 1], t)
            e_c = self.ge._E(live, cache)
            if t in eval_set:
                out[t] = e_c
            if act_policy and t in slot_set and t >= first_slot and m > 0 and self.T - 1 - t > self.d:
                tabu = (t - touched) < self.cool
                pairs = candidate_pairs(self.n, self.eu, self.ev, self.length, conf, live, down[t - k - 1], tabu, self.budget, self.rules, 1, 1)
                if pairs:
                    a, r = pairs[0]
                    li = live.copy()
                    if r is not None:
                        li[r] = False
                    E_i = self.ge._E(li, cache)
                    li[a] = True
                    E_f = self.ge._E(li, cache)
                    tau_t = self.T - 1 - t
                    R = self.d * (e_c - E_i) + (e_c - E_f) * max(0, tau_t - self.d)
                    if R > self.prm.c_op + hurdle:                   # hurdle = 0: the original base policy (Fix 2 raises it to model reserving a unit)
                        conf, ready, touched = self._apply(conf, ready, touched, (a, r), t)
                        m -= 1
        return out

    def _epochs(self, k, s):
        """Evaluation epochs of scenario s and their weights: dense for the setup window and first slot (so that a one-epoch delay of waiting is
        visible), then a strided tail with a stratified phase (s mod stride): systematic sampling, unbiased over scenarios."""
        stride, dense = self.prm.slot, self.d + 3
        last = self.T - 1
        te = list(range(k + 1, min(k + dense, last) + 1))
        w = {t: 1.0 for t in te}
        t = k + dense + 1 + (s % stride)
        while t <= last:
            te.append(t)
            w[t] = float(stride)
            t += stride
        return te, w

    # -------------------------------------------------------------- full-horizon candidate gain (Fix 1)
    def gain_full_many(self, configured, ready_at, last_touched, k, mutations, scen, cache=None):
        """End-of-run gain of each candidate (a list of (add, remove) tuples) on the scenario set, per scenario: array (S, L).
        Same dense-then-strided path and surrogate as price() (so gain_full == price().G_now for the same scenarios); the null path is computed
        once per scenario and shared by all candidates (common random numbers). No extrapolation (removes assumption A8 from candidate selection)."""
        tau = self.T - 1 - k
        assert scen.H >= tau, "full-horizon scenarios must reach the end of the run"
        cache = {} if cache is None else cache
        applied = [self._apply(configured, ready_at, last_touched, m, k) for m in mutations]
        out = np.zeros((scen.S, len(mutations)))
        for s in range(scen.S):
            down = scen.down[s]
            te, w = self._epochs(k, s)
            ev_set = set(te)
            e_null = self._path(configured, ready_at, last_touched, 0, down, k, ev_set, set(), 0, cache, False)
            for c, (conf_a, ready_a, touched_a) in enumerate(applied):
                e_a = self._path(conf_a, ready_a, touched_a, 0, down, k, ev_set, set(), 0, cache, False)
                out[s, c] = sum(w[t] * (e_null[t] - e_a[t]) for t in te)
        return out

    def gain_full(self, configured, ready_at, last_touched, k, mutation, scen, cache=None):
        """Per-scenario end-of-run gain of one candidate (array of length S)."""
        return self.gain_full_many(configured, ready_at, last_touched, k, [mutation], scen, cache)[:, 0]

    # -------------------------------------------------------------- budget reservation (Fix 2)
    def _values(self, configured, ready_at, last_touched, k, m_left, mutation, scen, hurdles, cache):
        """Per-scenario G_now (S,) and, for each base-policy hurdle h in `hurdles`, W_wait (S, F) and W_act (S, F): the same paths as price(), with
        the base policy acting only if its estimated net reward exceeds c_op + h in BOTH the wait branch and the continuation after acting."""
        tau = self.T - 1 - k
        assert scen.H >= tau, "rollout scenarios must reach the end of the run"
        stride = self.prm.slot
        slots_wait, slots_act = set(range(k + 1, self.T, stride)), set(range(k + 2, self.T, stride))
        conf_a, ready_a, touched_a = self._apply(configured, ready_at, last_touched, mutation, k)
        Gn, Ww, Wa = np.zeros(scen.S), np.zeros((scen.S, len(hurdles))), np.zeros((scen.S, len(hurdles)))
        for s in range(scen.S):
            down = scen.down[s]
            te, w = self._epochs(k, s)
            ev_set = set(te)
            e_null = self._path(configured, ready_at, last_touched, 0, down, k, ev_set, set(), 0, cache, False)
            e_a = self._path(conf_a, ready_a, touched_a, 0, down, k, ev_set, set(), 0, cache, False)
            Gn[s] = sum(w[t] * (e_null[t] - e_a[t]) for t in te)
            for f, h in enumerate(hurdles):
                e_wait = self._path(configured, ready_at, last_touched, m_left, down, k, ev_set, slots_wait, k + 1, cache, True, h)
                e_act = self._path(conf_a, ready_a, touched_a, m_left - 1, down, k, ev_set, slots_act, k + 2, cache, True, h)
                Ww[s, f] = sum(w[t] * (e_null[t] - e_wait[t]) for t in te)
                Wa[s, f] = sum(w[t] * (e_null[t] - e_act[t]) for t in te)
        return Gn, Ww, Wa

    def base_reward_now(self, configured, ready_at, down_now, k, mutation):
        """The base policy's own net-reward statistic R for `mutation` in the CURRENT state (same formula as inside _path):
        R* = d (E_c - E_interim) + (E_c - E_final) max(0, tau - d). This is the scale in which the hurdle is expressed."""
        live = self._live(configured, ready_at, down_now, k)
        cache = {}
        e_c = self.ge._E(live, cache)
        li = live.copy()
        if mutation[1] is not None:
            li[mutation[1]] = False
        e_i = self.ge._E(li, cache)
        if mutation[0] is not None:
            li[mutation[0]] = True
        e_f = self.ge._E(li, cache)
        return self.d * (e_c - e_i) + (e_c - e_f) * max(0, self.T - 1 - k - self.d)

    def reserve_check(self, configured, ready_at, last_touched, down_now, k, m_left, mutation, scen_sel, scen_test, factors):
        """One-step rollout with a hurdle family (Fix 2). Step 1 (test scenarios, hurdle 0): the original comparison; if it says wait, stop.
        Step 2 (INDEPENDENT selection scenarios): scale = R* (the base policy's own statistic for a* now, see base_reward_now); for hurdles
        h_f = f * scale, f in {0} + factors ('wait for an opportunity at least f times as good as the present one'), pick the wait-branch and
        act-continuation hurdles with the highest expected value (ties -> smaller hurdle). Step 3 (test scenarios): re-evaluate with the chosen
        hurdles. Act only if both comparisons favour acting, so the rule is never more eager than the one-step rule."""
        c_op = self.prm.c_op
        cache = {}
        Gn, Ww, Wa = self._values(configured, ready_at, last_touched, k, m_left, mutation, scen_test, [0.0], cache)
        adv0 = Wa[:, 0] - c_op - Ww[:, 0]
        n_ = float(Gn.mean() - c_op)
        lam = float(Ww[:, 0].mean() - (Wa[:, 0].mean() - Gn.mean()))
        se0 = float(adv0.std(ddof=1) / np.sqrt(len(adv0))) if len(adv0) > 1 else 0.0
        base = dict(N=n_, Lambda=lam, advantage0=float(adv0.mean()), se0=se0, W_wait0=float(Ww[:, 0].mean()), W_act0=float(Wa[:, 0].mean()))
        if not adv0.mean() > 0:                                  # the one-step rule already says wait: nothing to check
            return ReserveResult(**base, advantage=float(adv0.mean()), f_wait=0.0, f_act=0.0, scale=math.nan, act=False, checked=False)
        if not [f for f in factors if f > 0]:                    # no hurdles requested: identical to the one-step rule
            return ReserveResult(**base, advantage=float(adv0.mean()), f_wait=0.0, f_act=0.0, scale=math.nan, act=True, checked=False)
        scale = max(self.base_reward_now(configured, ready_at, down_now, k, mutation) - c_op, 0.0)
        fam = [0.0] + [float(f) for f in factors if f > 0]
        _, sw, sa = self._values(configured, ready_at, last_touched, k, m_left, mutation, scen_sel, [f * scale for f in fam], cache)
        fw, fa = fam[int(np.argmax(sw.mean(axis=0)))], fam[int(np.argmax(sa.mean(axis=0)))]
        need = sorted({0.0, fw * scale, fa * scale})
        _, tw, ta = self._values(configured, ready_at, last_touched, k, m_left, mutation, scen_test, need, cache)
        iw, ia = need.index(fw * scale), need.index(fa * scale)
        adv = ta[:, ia] - c_op - tw[:, iw]
        return ReserveResult(**base, advantage=float(adv.mean()), f_wait=fw, f_act=fa, scale=scale, act=bool(adv0.mean() > 0 and adv.mean() > 0),
                             checked=True)

    # -------------------------------------------------------------- the shadow price
    def price(self, configured, ready_at, last_touched, k, m_left, mutation, scen) -> RolloutResult:
        """mutation = (add, remove) tuple, the candidate a*. scen must cover epochs k+1 .. T-1 (scen.H >= T - 1 - k)."""
        tau = self.T - 1 - k
        assert scen.H >= tau, "rollout scenarios must reach the end of the run"
        stride = self.prm.slot
        slots_wait = set(range(k + 1, self.T, stride))                   # pi0 slots if we wait: k+1, k+1+stride, ...
        slots_act = set(range(k + 2, self.T, stride))                    # after acting at k the cooldown pushes pi0's first slot to k+2
        cache = {}
        conf_a, ready_a, touched_a = self._apply(configured, ready_at, last_touched, mutation, k)
        Wa, Ww, Gn = np.zeros(scen.S), np.zeros(scen.S), np.zeros(scen.S)
        for s in range(scen.S):
            down = scen.down[s]
            te, w = self._epochs(k, s)
            ev_set = set(te)
            e_null = self._path(configured, ready_at, last_touched, 0, down, k, ev_set, set(), 0, cache, False)
            e_a = self._path(conf_a, ready_a, touched_a, 0, down, k, ev_set, set(), 0, cache, False)
            e_wait = self._path(configured, ready_at, last_touched, m_left, down, k, ev_set, slots_wait, k + 1, cache, True)
            e_act = self._path(conf_a, ready_a, touched_a, m_left - 1, down, k, ev_set, slots_act, k + 2, cache, True)
            Gn[s] = sum(w[t] * (e_null[t] - e_a[t]) for t in te)
            Ww[s] = sum(w[t] * (e_null[t] - e_wait[t]) for t in te)
            Wa[s] = sum(w[t] * (e_null[t] - e_act[t]) for t in te)
        c_op = self.prm.c_op
        adv = Wa - c_op - Ww
        N = float(Gn.mean() - c_op)
        lam = float(Ww.mean() - (Wa.mean() - Gn.mean()))
        return RolloutResult(W_wait=float(Ww.mean()), W_act=float(Wa.mean()), G_now=float(Gn.mean()), N=N, Lambda=lam,
                             advantage=float(adv.mean()), se=float(adv.std(ddof=1) / np.sqrt(scen.S)) if scen.S > 1 else 0.0,
                             act=bool(adv.mean() > 0), S=scen.S)
