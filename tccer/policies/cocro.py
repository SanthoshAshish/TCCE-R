"""COCRO v2 policy (docs/COCRO_DESIGN.md 2.8). [PROPOSED; nothing here is a claim of performance]

At the end of each epoch k:
  1. update the CFPE failure model with the observed link states;
  2. stop if the cap is reached, the cooldown is running, or no benefit epoch remains after the setup delay;
  3. candidates: up to K_r removals x K_a additions (cocro_ops), each re-checked by the UNCHANGED SafetyGate;
  4. selection on scenario set S_sel (short horizon d + H, gain G to the end of the run by extrapolation): a* = argmax G - c_op;
  5. act/wait on an independent scenario set S_test (cross-fitting) reaching the end of the run: rollout shadow price (opportunity.py):
     act iff E[W_act] - c_op > E[W_wait]; otherwise defer/reserve.
Variants (flags, registered under their own policy names): price='rollout' (full COCRO), 'zero' (act iff the net gain of a* is positive:
Lambda = 0), 'none' (COCRO-M: spend whenever cooled down, best-gain candidate even if its gain is negative: A7-like timing with COCRO selection);
plug_in (posterior mean instead of posterior draws); cross_fit=False (one scenario set for selection and test).
Self-registers into POLICIES on import (no existing file is modified); import this module before calling simulate().
Not implemented here: TRDE ledger/screen, delayed credit (kappa = 1, identity calibration map), persistence-valued removals.
The controller's scenario RNG is derived once from the policy stream [seed, 3] and then keyed by (epoch, role): independent of the environment.
"""
import math
from dataclasses import dataclass, replace

import numpy as np

from tccer.core.cocro_ops import Rules, candidate_pairs
from tccer.core.failure_model import CFPEParams, PropagationFailureModel
from tccer.core.mutations import Mutation
from tccer.core.opportunity import RolloutParams, RolloutPricer
from tccer.core.scenarios import ScenarioSampler, ScenarioSet, controller_rng
from tccer.core.selector import EMPTY_SELECTION
from tccer.core.value import GainEstimator
from tccer.policies import POLICIES
from tccer.policies.base import Policy

COOLDOWN = 2


@dataclass(frozen=True)
class CocroParams:
    S_sel: int = 16
    S_test: int = 16
    H: int = 5                  # benefit window after the setup delay
    Kr: int = 3
    Ka: int = 8
    slot: int = 4               # base-policy slot spacing / path stride
    phi: float = 0.98           # CFPE forgetting
    c_op: float = 0.0
    estimator: str = "exact"    # 'exact' spectral surrogate or 'laplacian'
    price: str = "rollout"      # 'rollout' | 'zero' | 'none'
    plug_in: bool = False
    cross_fit: bool = True
    reserve_factors: tuple = ()  # Fix 2: hurdle family (multiples of the base policy's reward statistic R* for a*) for budget reservation; () = original one-step rule
    shortlist: int = 0          # Fix 1: >0 = rerank the top-`shortlist` candidates by the full-horizon gain (0 = original extrapolated-gain argmax)

    @staticmethod
    def fast(**kw):
        """Reduced sampling for development-seed diagnostics (documented deviation from the design defaults)."""
        return CocroParams(S_sel=8, S_test=8, H=3, Kr=2, Ka=5, **kw)


def select_candidate(ge, pricer, configured, ready_at, last_touched, k, feas, sel_short, sel_full, tau, shortlist, c_op):
    """Pick the candidate to evaluate. shortlist == 0: argmax of the extrapolated gain G = S_setup + b (tau - d) (original behaviour, assumption A8).
    shortlist > 0 (Fix 1): shortlist by the cheap extrapolated G, then choose by the FULL-horizon simulated gain on the selection scenarios
    (sel_full must reach the end of the run; it shares its first d + H epochs with sel_short). Returns a dict with the chosen index and diagnostics."""
    g = ge.estimate(configured, ready_at, k, sel_short, feas, tau)
    j0 = int(np.argmax(g.G - c_op))
    if shortlist <= 0:
        return dict(j=j0, G=float(g.G[j0]), se=float(g.se[j0]), G_full=math.nan, changed=math.nan)
    order = np.argsort(-(g.G - c_op), kind="stable")[:min(shortlist, len(feas))]
    gf = pricer.gain_full_many(configured, ready_at, last_touched, k, [(feas[i].add, feas[i].remove) for i in order], sel_full)
    mean = gf.mean(axis=0)
    jj = int(np.argmax(mean))
    j = int(order[jj])
    return dict(j=j, G=float(g.G[j]), se=float(g.se[j]), G_full=float(mean[jj]), changed=float(j != j0))


class CocroArm(Policy):
    name = "cocro"
    params = CocroParams()

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.base = int(rng.integers(2 ** 62))          # controller stream base, drawn once from the policy stream [seed, 3]
        self.model = self.sampler = self.ge = self.pricer = None
        self.rules = Rules(d_max=cfg.d_max if cfg.degree_fix else None, degree_basis=cfg.degree_basis,
                           failed_link_value=cfg.failed_link_value, strict_budget=cfg.budget_on == "configured")
        self.stats = dict(evaluated=0, acted=0, deferred=0, no_gain=0, no_cand=0, reserved=0)
        self._clear()

    def _clear(self):
        self.d = dict(cocro_evaluated=0, cocro_n_cand=0, cocro_G=math.nan, cocro_se=math.nan, cocro_N=math.nan, cocro_Lambda=math.nan,
                      cocro_adv=math.nan, cocro_adv_se=math.nan, cocro_W_wait=math.nan, cocro_W_act=math.nan, cocro_lift=math.nan,
                      cocro_h0=math.nan, cocro_Gfull=math.nan, cocro_rank_changed=math.nan,
                      cocro_adv_res=math.nan, cocro_res_fw=math.nan, cocro_res_fa=math.nan, cocro_decision="")

    def _init(self, state):
        p, cfg = self.params, self.cfg
        self.model = PropagationFailureModel(state.n, state.eu, state.ev, CFPEParams(phi=p.phi))
        self.sampler = ScenarioSampler(self.model)
        self.ge = GainEstimator(state.n, state.eu, state.ev, cfg.rounds_per_epoch, cfg.eps, cfg.p_transient, cfg.link_setup_epochs, p.H,
                                mode=p.estimator)
        self.pricer = RolloutPricer(state.n, state.eu, state.ev, state.length, self.ge, self.rules, cfg.link_setup_epochs, cfg.edge_cooldown,
                                    self.pipeline.budget, cfg.epochs, RolloutParams(slot=p.slot, c_op=p.c_op))

    def decide(self, k, obs, state):
        p, cfg = self.params, self.cfg
        self._clear()
        if self.model is None:
            self._init(state)
        self.model.update(state.down, state.configured, k)
        M = cfg.mutation_cap
        if M is not None and self.n_mutations >= M:
            self.pipeline.last["select_outcome"] = "capped"
            return None
        if self.last_mutation_epoch is not None and k - self.last_mutation_epoch < COOLDOWN:
            return None
        d, tau = cfg.link_setup_epochs, cfg.epochs - 1 - k
        if tau - d <= 0:
            return None
        m_left = (M - self.n_mutations) if M is not None else 10 ** 6
        live, tabu = state.live_mask(), self.pipeline.tabu(k)
        pairs = candidate_pairs(state.n, state.eu, state.ev, state.length, state.configured, live, state.down, tabu, self.pipeline.budget,
                                self.rules, p.Kr, p.Ka)
        feas = [Mutation(add=a, remove=r) for a, r in pairs if self.pipeline.gate.check(state, Mutation(add=a, remove=r), tabu)[0]]
        self.pipeline.last = dict(EMPTY_SELECTION, n_candidates=len(feas),
                                  select_outcome="no_candidates" if not pairs else ("all_rejected" if not feas else ""))
        self.d["cocro_n_cand"] = len(feas)
        if not feas:
            self.stats["no_cand"] += 1
            return None
        self.d["cocro_evaluated"] = 1
        self.stats["evaluated"] += 1
        Hs = d + p.H
        sel_full = None
        if p.cross_fit:
            if p.shortlist > 0 or p.reserve_factors:   # the selection scenarios must reach the end of the run; the sampler's prefix property makes the first Hs epochs identical
                sel_full = self.sampler.sample(p.S_sel, max(tau, Hs), controller_rng(self.base, k, 1), p.plug_in)
                sel = ScenarioSet(down=sel_full.down[:, :Hs], node_down=sel_full.node_down[:, :Hs], k=k, thetas=sel_full.thetas)
            else:
                sel = self.sampler.sample(p.S_sel, Hs, controller_rng(self.base, k, 1), p.plug_in)
            full = self.sampler.sample(p.S_test, tau, controller_rng(self.base, k, 2), p.plug_in) if p.price == "rollout" else None
        else:
            full = self.sampler.sample(max(p.S_sel, p.S_test), max(tau, Hs), controller_rng(self.base, k, 1), p.plug_in)   # must also cover the selection window d + H
            sel = ScenarioSet(down=full.down[:, :Hs], node_down=full.node_down[:, :Hs], k=k, thetas=full.thetas)
            sel_full = full
        pick = select_candidate(self.ge, self.pricer, state.configured, state.ready_at, self.pipeline.last_touched, k, feas, sel, sel_full, tau,
                                p.shortlist, p.c_op)
        j = pick["j"]
        a = feas[j]
        gate_gain = pick["G_full"] if p.shortlist > 0 else pick["G"]
        self.d.update(cocro_G=pick["G"], cocro_se=pick["se"], cocro_Gfull=pick["G_full"], cocro_rank_changed=pick["changed"],
                      cocro_lift=self.model.lift(), cocro_h0=float(self.model.map_theta().h[0]))
        if p.price == "none":                                    # COCRO-M: spend whenever possible with the best-gain candidate
            act = True
        elif gate_gain - p.c_op <= 0:                            # even the selection estimate (full-horizon if shortlist > 0) sees no net gain
            act = False
            self.stats["no_gain"] += 1
            self.d["cocro_decision"] = "no_gain"
        elif p.price == "zero":                                  # Lambda = 0: act iff the net gain, on independent scenarios, is positive
            test = self.sampler.sample(p.S_test, Hs, controller_rng(self.base, k, 2), p.plug_in)
            n_test = float(self.ge.estimate(state.configured, state.ready_at, k, test, [a], tau).G[0]) - p.c_op
            self.d["cocro_N"] = n_test
            act = n_test > 0
        else:                                                    # rollout shadow price on the independent (or shared) full-horizon set
            if p.reserve_factors:                                # Fix 2: one-step rollout with a hurdle family, hurdles chosen on the independent set sel_full
                rr = self.pricer.reserve_check(state.configured, state.ready_at, self.pipeline.last_touched, state.down, k, m_left, (a.add, a.remove), sel_full,
                                               full, p.reserve_factors)
                self.d.update(cocro_N=rr.N, cocro_Lambda=rr.Lambda, cocro_adv=rr.advantage0, cocro_adv_se=rr.se0, cocro_W_wait=rr.W_wait0,
                              cocro_W_act=rr.W_act0, cocro_adv_res=rr.advantage, cocro_res_fw=rr.f_wait, cocro_res_fa=rr.f_act)
                act = rr.act
                if rr.checked and not rr.act:                    # the one-step rule said act, the hurdle comparison says keep the unit
                    self.stats["reserved"] += 1
                    self.d["cocro_decision"] = "reserve"
            else:
                r = self.pricer.price(state.configured, state.ready_at, self.pipeline.last_touched, k, m_left, (a.add, a.remove), full)
                self.d.update(cocro_N=r.N, cocro_Lambda=r.Lambda, cocro_adv=r.advantage, cocro_adv_se=r.se, cocro_W_wait=r.W_wait, cocro_W_act=r.W_act)
                act = r.act
        if not act:
            self.stats["deferred"] += 1
            self.d["cocro_decision"] = self.d["cocro_decision"] or "defer"
            self.pipeline.last["select_outcome"] = "deferred"
            return None
        self.d["cocro_decision"] = "act"
        self.stats["acted"] += 1
        self.n_mutations += 1
        self.last_mutation_epoch = k
        self.pipeline.last.update(select_outcome="mutated", removed_failed_link=bool(a.remove is not None and not live[a.remove]))
        return a

    def info(self):
        return dict(self.d, cocro_acted_total=self.stats["acted"], cocro_deferred_total=self.stats["deferred"],
                    cocro_no_gain_total=self.stats["no_gain"], cocro_evaluated_total=self.stats["evaluated"],
                    cocro_reserved_total=self.stats["reserved"])


def register_variant(name, **overrides):
    """Register a COCRO variant under `name` with CocroParams overrides (e.g. register_variant('cocro_f', **FAST))."""
    base = overrides.pop("base", CocroParams())
    cls = type(f"Cocro_{name}", (CocroArm,), {"name": name, "params": replace(base, **overrides)})
    POLICIES[name] = cls
    return cls


register_variant("cocro")
register_variant("cocro_m", price="none")
register_variant("cocro_l0", price="zero")
register_variant("cocro_plugin", plug_in=True)
register_variant("cocro_nocf", cross_fit=False)
register_variant("cocro_r", reserve_factors=(1.0, 2.0))            # Fix 2 only: budget reservation by a hurdle family (design 12)
register_variant("cocro_fg", shortlist=3)                  # Fix 1: full-horizon rerank of the top-3 candidates (design 2.3/10)
register_variant("cocro_fgr", shortlist=3, reserve_factors=(1.0, 2.0))   # Fix 1 + Fix 2
