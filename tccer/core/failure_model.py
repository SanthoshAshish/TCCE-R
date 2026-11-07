"""COCRO v2, component CFPE: online failure model with lagged-adjacency propagation, a censored downtime mixture and node-level events.
[PROPOSED; docs/COCRO_DESIGN.md 2.2]. Nothing here is a claim of causal identification: the lift is a lagged-adjacency association.

Observed per epoch (all potential links are observable, assumption A2'): the down mask. Estimated, with exponential forgetting phi per epoch:
  * bucketed lagged-adjacency failure hazard  h[N]: probability that an up link fails in an epoch given that N adjacent links (sharing a node)
    were down in the PREVIOUS epoch (N = 0, 1, ..., nb-1 with the last bucket open). Beta posteriors; empirical-Bayes partial pooling:
    bucket 0 has a prior mean prior_h, buckets N > 0 use the posterior mean of bucket 0 as prior mean (so lift appears only if the data support it).
    (The design text uses h*lambda^N; the bucketed form is a nonparametric superset and is what is implemented. lambda_hat = h[1]/h[0].)
  * downtime as a two-component geometric mixture (short r_s > long r_l, weight w of the long one) fitted by EM with RIGHT-CENSORED ongoing
    episodes (an ongoing episode of age a contributes (1-r)^a, a completed one of length a contributes (1-r)^(a-1) r) and weak priors.
  * node events: a node is flagged down in an epoch when it has >= 2 configured incident links and all of them are down; link failures at flagged
    nodes are attributed to the node and are excluded from the link-level statistics (hazard buckets and downtime episodes).
Not implemented in this increment (stated, not hidden): per-link heterogeneous hazards (pooled per bucket), spatial common-cause shocks,
change-point detection beyond forgetting.
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class CFPEParams:
    phi: float = 0.98              # forgetting per epoch
    prior_h: float = 0.02          # prior failure hazard (bucket 0)
    prior_w: float = 20.0          # prior strength in pseudo link-epochs
    prior_r: float = 0.10          # prior repair probability (both mixture components before data)
    nb: int = 4                    # hazard buckets N = 0, 1, 2, 3+
    node_prior_h: float = 0.005
    node_prior_r: float = 0.2
    node_prior_w: float = 30.0
    min_episodes: float = 6.0      # weighted episodes needed before the mixture is fitted (else a one-component prior)
    em_iters: int = 25
    rate_prior_trials: float = 5.0  # pseudo-trials of the prior on each mixture rate


@dataclass
class Theta:
    """One parameter draw (or the posterior-mean point estimate)."""
    h: np.ndarray                  # failure hazard per adjacency bucket
    w: float                       # P(a new episode is of the long component)
    r_s: float
    r_l: float
    node_h: float
    node_r: float


def fit_mixture(dur, cens, wt, prm: CFPEParams, init=(0.5, 0.5, 0.05)):
    """Weighted EM for the two-component geometric mixture with right censoring. dur >= 1 (epochs down); cens True = still down at age dur.
    Returns (w_long, r_short, r_long) with r_short >= r_long."""
    dur, cens, wt = np.asarray(dur, float), np.asarray(cens, bool), np.asarray(wt, float)
    w, rs, rl = init
    if len(dur) == 0 or wt.sum() <= 0:
        return 0.5, prm.prior_r, prm.prior_r
    ev = (~cens).astype(float)
    n0, r0 = prm.rate_prior_trials, prm.prior_r
    for _ in range(prm.em_iters):
        def lik(r):                                          # per-episode likelihood under a geometric component
            return np.where(cens, (1 - r) ** dur, (1 - r) ** (dur - 1) * r)
        ls, ll = (1 - w) * lik(rs), w * lik(rl)
        g = ll / np.maximum(ls + ll, 1e-300)                 # responsibility of the long component
        wl, ws = wt * g, wt * (1 - g)
        w = float((wl.sum() + 1.0) / (wt.sum() + 2.0))       # Beta(1,1) prior on the weight
        rl = float(np.clip(((wl * ev).sum() + n0 * r0) / ((wl * dur).sum() + n0), 1e-3, 0.99))   # events / trials, weak common prior
        rs = float(np.clip(((ws * ev).sum() + n0 * r0) / ((ws * dur).sum() + n0), 1e-3, 0.99))
        if rs < rl:                                          # keep the labelling: short = faster repair
            rs, rl, w = rl, rs, 1 - w
    return float(w), float(rs), float(rl)


def persistence_prob(age, theta: Theta, horizon):
    """P(remaining downtime > horizon epochs | the link has been down `age` epochs, theta) under the mixture; vectorised in age.
    Posterior over components given survival to age a: proportional to weight * (1-r)^a (memoryless within a component)."""
    a = np.asarray(age, float)
    ws, wl = (1 - theta.w) * (1 - theta.r_s) ** a, theta.w * (1 - theta.r_l) ** a
    post_l = wl / np.maximum(ws + wl, 1e-300)
    return post_l * (1 - theta.r_l) ** horizon + (1 - post_l) * (1 - theta.r_s) ** horizon


class PropagationFailureModel:
    def __init__(self, n, eu, ev, params: CFPEParams = CFPEParams()):
        self.n, self.eu, self.ev, self.prm = n, np.asarray(eu), np.asarray(ev), params
        self.P = len(self.eu)
        self.nb_n = np.zeros(params.nb)                     # decayed up link-epochs per bucket
        self.nb_f = np.zeros(params.nb)                     # decayed failures per bucket
        self.node_n = self.node_f = self.node_dn = self.node_rep = 0.0
        self.episodes = []                                  # [duration, end_epoch] of completed link episodes (not node-attributed)
        self.prev_down = None
        self.age = np.zeros(self.P, dtype=int)
        self.ep_excluded = np.zeros(self.P, dtype=bool)
        self.node_down = np.zeros(n, dtype=bool)
        self.k = -1

    # ------------------------------------------------------------------ observation update
    def _node_flags(self, down, configured):
        cfgd = configured.astype(float)
        deg = np.bincount(self.eu, weights=cfgd, minlength=self.n) + np.bincount(self.ev, weights=cfgd, minlength=self.n)
        dd = configured & down
        ddeg = np.bincount(self.eu, weights=dd.astype(float), minlength=self.n) + np.bincount(self.ev, weights=dd.astype(float), minlength=self.n)
        return (deg >= 2) & (ddeg == deg)

    def update(self, down, configured, k):
        """Feed the observed down mask (all potential links) and the configured mask for epoch k (call once per epoch, in order)."""
        down = np.asarray(down, bool)
        nodes = self._node_flags(down, np.asarray(configured, bool))
        prm = self.prm
        if self.prev_down is None:
            self.prev_down, self.k = down.copy(), k
            self.age = down.astype(int)
            self.ep_excluded = (nodes[self.eu] | nodes[self.ev]) & down
            self.node_down = nodes
            return
        assert k == self.k + 1, "epochs must be observed in order"
        prev = self.prev_down
        dn = np.bincount(self.eu, weights=prev.astype(float), minlength=self.n) + np.bincount(self.ev, weights=prev.astype(float), minlength=self.n)
        N = np.minimum((dn[self.eu] + dn[self.ev]).astype(int), prm.nb - 1)    # previous-epoch exposure (an up link has prev_down = 0)
        attributed = nodes[self.eu] | nodes[self.ev]
        self.nb_n *= prm.phi
        self.nb_f *= prm.phi
        valid = ~prev & ~attributed
        np.add.at(self.nb_n, N[valid], 1.0)
        np.add.at(self.nb_f, N[valid & down], 1.0)
        # node events (nodes with >= 2 configured incident links are the eligible ones)
        self.node_n *= prm.phi; self.node_f *= prm.phi; self.node_dn *= prm.phi; self.node_rep *= prm.phi
        self.node_n += float((~self.node_down).sum())
        self.node_f += float((nodes & ~self.node_down).sum())
        self.node_dn += float(self.node_down.sum())
        self.node_rep += float((~nodes & self.node_down).sum())
        # downtime episodes
        ended = prev & ~down & ~self.ep_excluded
        for e in np.flatnonzero(ended):
            self.episodes.append([int(self.age[e]), k])
        began = down & ~prev
        self.age = np.where(down, np.where(prev, self.age + 1, 1), 0)
        self.ep_excluded = np.where(began, attributed, np.where(down, self.ep_excluded, False))
        self.node_down = nodes
        self.prev_down, self.k = down.copy(), k
        self.episodes = [ep for ep in self.episodes if prm.phi ** (k - ep[1]) > 1e-3]

    # ------------------------------------------------------------------ estimates
    def _hazard_params(self):
        prm = self.prm
        a0 = prm.prior_h * prm.prior_w + self.nb_f[0]
        b0 = (1 - prm.prior_h) * prm.prior_w + self.nb_n[0] - self.nb_f[0]
        pool = a0 / (a0 + b0)                              # empirical-Bayes prior mean for the exposed buckets
        a, b = np.empty(prm.nb), np.empty(prm.nb)
        a[0], b[0] = a0, max(b0, 1e-9)
        for i in range(1, prm.nb):
            a[i] = pool * prm.prior_w + self.nb_f[i]
            b[i] = max((1 - pool) * prm.prior_w + self.nb_n[i] - self.nb_f[i], 1e-9)
        return a, b

    def _mixture_data(self, boot_rng=None):
        k = self.k
        dur = [e[0] for e in self.episodes]
        wt = [self.prm.phi ** (k - e[1]) for e in self.episodes]
        cens = [False] * len(dur)
        if self.prev_down is not None:                      # ongoing, non-attributed episodes: right-censored at their current age
            on = np.flatnonzero(self.prev_down & ~self.ep_excluded)
            dur += list(self.age[on]); wt += [1.0] * len(on); cens += [True] * len(on)
        wt = np.array(wt, float)
        if boot_rng is not None and len(wt):                # Bayesian bootstrap: Dirichlet(1,...,1) reweighting
            wt = wt * boot_rng.dirichlet(np.ones(len(wt))) * len(wt)
        return np.array(dur, float), np.array(cens, bool), wt

    def _mixture(self, boot_rng=None):
        dur, cens, wt = self._mixture_data(boot_rng)
        if wt.sum() < self.prm.min_episodes:
            return 0.5, self.prm.prior_r, self.prm.prior_r
        return fit_mixture(dur, cens, wt, self.prm)

    def _node_params(self, rng=None):
        p = self.prm
        ah, bh = p.node_prior_h * p.node_prior_w + self.node_f, (1 - p.node_prior_h) * p.node_prior_w + self.node_n - self.node_f
        ar, br = p.node_prior_r * p.node_prior_w + self.node_rep, (1 - p.node_prior_r) * p.node_prior_w + self.node_dn - self.node_rep
        if rng is None:
            return ah / (ah + bh), ar / (ar + br)
        return float(rng.beta(ah, max(bh, 1e-9))), float(rng.beta(ar, max(br, 1e-9)))

    def map_theta(self) -> Theta:
        """Posterior-mean (plug-in) parameters."""
        a, b = self._hazard_params()
        w, rs, rl = self._mixture()
        nh, nr = self._node_params()
        return Theta(a / (a + b), w, rs, rl, nh, nr)

    def sample_theta(self, rng) -> Theta:
        """One posterior draw: independent Beta draws for the hazards and node rates; the mixture by a Bayesian-bootstrap refit (censored EM)."""
        a, b = self._hazard_params()
        w, rs, rl = self._mixture(boot_rng=rng)
        nh, nr = self._node_params(rng)
        return Theta(rng.beta(a, b), w, rs, rl, nh, nr)

    def lift(self, theta: Theta = None):
        """Reported association: lambda_hat = h[1] / h[0] (not a causal claim)."""
        th = theta or self.map_theta()
        return float(th.h[1] / th.h[0]) if len(th.h) > 1 else 1.0

    def persistence(self, horizon, theta: Theta = None):
        """Per-link persistence probability of the currently down links (0 for up or node-attributed links)."""
        th = theta or self.map_theta()
        out = persistence_prob(self.age, th, horizon)
        return np.where(self.prev_down & ~self.ep_excluded, out, 0.0)
