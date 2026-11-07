"""Causality-aware resilience-debt ledger (Revision 2, component TRDE).  [PROPOSED mechanism; not an established result]

The v0.7/v0.8 debt is a CUSUM of an instantaneous stress, D_k = max(0, D_{k-1} + s_k - kappa), reset to 0 after any
accepted mutation. It cannot say *why* the stress is high, whether it is still caused by open damage, or whether a
mutation repaid anything. This ledger instead keeps one liability item per open link-failure episode and charges
consensus error only to damage that is actually open.

Per epoch k, for every configured link e:
  criticality  c_e = (f_u - f_v)^2 / lambda2  from the Fiedler vector f of the *configured* graph (sum_e c_e = 1):
               the first-order share of algebraic connectivity carried by e (a proxy; first order only).
  episode      a maximal run of consecutive epochs with e configured and physically down; age = run length so far.
  charge       q_e = w_e * c_e * (1 + lam_E * E_k) while the episode is open, with the cause-class weight
                 w_e = rho_t   (< 1) for a temporary episode (age < tau),
                 w_e = 1       for a persistent episode (age >= tau),
                 times w_prop (>= 1) if the episode began adjacent (sharing a node) to a link that was down at k-1
                 (propagated failure; causal order is strict: only strictly earlier failures count as causes).
  E_k is charged only through open episodes: error with no open damage creates no debt.

Settlement of an episode (at the first epoch it is no longer open):
  link no longer configured (a mutation removed it)     -> written off in full (structurally compensated);
  link repaired, age < tau (temporary disturbance)       -> written off in full;
  link repaired, age >= tau (persistent damage cleared)  -> written off, but a scar sigma * accrued remains.
Scar decays by gamma per epoch only while E_k <= e_ok (recovery must be visible in consensus error: genuine recovery).

Debt:   D_k = sum_open accrued + scar + w_pred * sum_{e up} h_e * c_e,
the last term being an optional forward (predicted-failure) liability, recomputed each epoch and never accumulated;
h_e is the estimated per-epoch failure hazard, multiplied by w_prop for links adjacent to a currently-down link.

There is no blanket reset after a mutation: debt falls only through settlement, so an action that does not remove or
outlast the damage leaves the debt standing. Everything here is computed from quantities the controller observes
(link up/down states and consensus error); nothing uses future information.
"""
import numpy as np

from tccer.metrics.resilience import lambda2_fiedler


def setup_derived_tau(cfg) -> int:
    """Persistence age derived from the setup delay d (no tuning): a response decided when a failure is first seen is usable
    from epoch onset + 1 + d, so it can only help against failures that last at least d + 2 epochs. Episodes shorter than
    that can never be remedied by rewiring and are 'temporary' from the controller's viewpoint: tau = d + 2."""
    return cfg.link_setup_epochs + 2


class CausalDebtLedger:
    def __init__(self, cfg, state_n, eu, ev):
        self.n, self.eu, self.ev = state_n, np.asarray(eu), np.asarray(ev)
        P = len(self.eu)
        self.tau, self.rho_t, self.w_prop = cfg.cd_tau, cfg.cd_rho_t, cfg.cd_w_prop
        self.sigma, self.gamma, self.e_ok = cfg.cd_scar, cfg.cd_gamma, cfg.cd_e_ok
        self.lam_E, self.w_pred = cfg.cd_lam_E, cfg.cd_w_pred
        self.age = np.zeros(P, dtype=int)
        self.acc = np.zeros(P)
        self.cascaded = np.zeros(P, dtype=bool)
        self.prev_down = np.zeros(P, dtype=bool)
        self.scar = 0.0
        self.D = 0.0
        self._crit_key, self._crit = None, None
        self.n_temporary = self.n_recovered = self.n_compensated = self.n_cascaded = self.n_persistent = 0
        self.pred = 0.0

    def criticality(self, configured):
        key = configured.tobytes()
        if key != self._crit_key:
            c = np.zeros(len(configured))
            idx = np.flatnonzero(configured)
            lam, f = lambda2_fiedler(self.n, self.eu[idx], self.ev[idx])
            if lam > 1e-9:
                c[idx] = (f[self.eu[idx]] - f[self.ev[idx]]) ** 2 / lam
            elif len(idx):
                c[idx] = 1.0 / len(idx)
            self._crit_key, self._crit = key, c
        return self._crit

    def update(self, state, E_hat, hazard=None):
        """Advance the ledger by one epoch from the observed link states and consensus error; returns D_k."""
        cfg_mask, down = state.configured, state.down
        open_now = cfg_mask & down
        c = self.criticality(cfg_mask)

        # 1. settle episodes that are no longer open
        was_open = self.acc > 0
        closed = was_open & ~open_now
        for e in np.flatnonzero(closed):
            if not cfg_mask[e]:
                self.n_compensated += 1
            elif self.age[e] < self.tau:
                self.n_temporary += 1
            else:
                self.n_recovered += 1
                self.scar += self.sigma * self.acc[e]
            self.acc[e] = 0.0
        self.age[~open_now] = 0
        self.cascaded[~open_now] = False

        # 2. open / continue episodes and charge them
        touched = np.zeros(self.n, dtype=bool)
        pd_ = np.flatnonzero(self.prev_down & cfg_mask)
        touched[self.eu[pd_]] = touched[self.ev[pd_]] = True
        for e in np.flatnonzero(open_now):
            self.age[e] += 1
            if self.age[e] == 1:
                self.cascaded[e] = bool(touched[self.eu[e]] or touched[self.ev[e]])
                self.n_cascaded += int(self.cascaded[e])
            self.n_persistent += int(self.age[e] == self.tau)      # episodes that reach persistent status (counter only)
            w = self.rho_t if self.age[e] < self.tau else 1.0
            if self.cascaded[e]:
                w *= self.w_prop
            self.acc[e] += w * c[e] * (1.0 + self.lam_E * E_hat)
        self.prev_down = open_now.copy()

        # 3. scar decays only on visible consensus recovery
        if E_hat <= self.e_ok:
            self.scar *= self.gamma

        # 4. forward liability from predicted failures (not accumulated)
        self.pred = 0.0
        if self.w_pred > 0 and hazard is not None:
            h = hazard[0]
            up = cfg_mask & ~down
            t2 = np.zeros(self.n, dtype=bool)
            dd = np.flatnonzero(open_now)
            t2[self.eu[dd]] = t2[self.ev[dd]] = True
            lift = np.where(t2[self.eu] | t2[self.ev], self.w_prop, 1.0)
            self.pred = float(self.w_pred * np.sum(np.minimum(0.9, h * lift)[up] * c[up]))

        self.D = float(self.acc.sum() + self.scar + self.pred)
        return self.D

    def info(self):
        return {"cd_open": int((self.acc > 0).sum()), "cd_open_debt": float(self.acc.sum()), "cd_scar": self.scar,
                "cd_pred": self.pred, "cd_temporary": self.n_temporary, "cd_recovered": self.n_recovered,
                "cd_compensated": self.n_compensated, "cd_cascaded": self.n_cascaded,
                "cd_persistent": self.n_persistent}
