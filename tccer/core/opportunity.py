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

    def _path(self, conf, ready, touched, m, down, k, eval_set, slot_set, first_slot, cache, act_policy):
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
                    if R > self.prm.c_op:
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
