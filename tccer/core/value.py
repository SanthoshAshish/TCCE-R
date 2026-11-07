"""COCRO v2, component CMVE (forward part): expected marginal future resilience gain of a candidate mutation. [PROPOSED; docs/COCRO_DESIGN.md 2.3]

Surrogate error of a graph (Metropolis consensus, T rounds, tolerance eps):
  exact spectral  E^(Q) = 1 - min(1, -0.5 ln( sum_{i>=2} lambda_i(W)^(2T) / (n-1) ) / ln(1/eps)),
     exact for the expected squared contraction under i.i.d. centred x(0) [linear algebra]; per-round transient failures enter through survival-
     scaled edge weights (an approximation: Jensen gap); disconnected graph -> 1 (component logic is exact); clipped to [0, 1] like the metric.
  Laplacian bound (large n): rho_L = 1 - q*lambda2(L)/(1 + d_max)  (Metropolis weights >= 1/(1+d_max), so this bounds the contraction factor),
     E_L = 1 - min(1, T * (-ln rho_L) / ln(1/eps)). A SURROGATE whose ranking agreement with the spectral value is a hypothesis to be checked.
Gain of an action a at decision epoch k, over S scenarios of the next H_s = d + H epochs (setup delay d, benefit window H):
  delta_t = E^(Q_t^null) - E^(Q_t^a)  with Q^a: removed link absent from k+1, added link usable from k+1+d, scenario link failures applied to both;
  S_setup = mean_s sum_{t=k+1}^{k+d} delta_t ;  b = mean_s mean_{t=k+d+1}^{k+d+H} delta_t ;
  G(a) = S_setup + kappa * b * max(0, tau_k - d)   (gain to the end of the run; tau_k = remaining epochs after k; assumption A8: stationary rate b),
  G_imm = S_setup + kappa * b * max(0, H0 - d) with H0 = d + 1, G_fut = G - G_imm. The null action has G = 0.
An optional monotone calibration map (isotonic regression of realised on predicted E) is applied to E^ before differencing; identity until fitted.
"""
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components


# ------------------------------------------------------------------ graph helpers
def _n_components(n, eu, ev):
    if len(eu) == 0:
        return n
    A = csr_matrix((np.ones(len(eu)), (eu, ev)), shape=(n, n))
    return connected_components(A, directed=False)[0]


def metropolis_W(n, eu, ev, q=1.0):
    """Metropolis matrix with survival-scaled edge weights (expected-degree weights, as the B8 predictor)."""
    if len(eu) == 0:
        return np.eye(n)
    d = np.bincount(eu, weights=np.full(len(eu), q), minlength=n) + np.bincount(ev, weights=np.full(len(eu), q), minlength=n)
    w = q / (1.0 + np.maximum(d[eu], d[ev]))
    W = np.zeros((n, n))
    np.add.at(W, (eu, ev), w)
    np.add.at(W, (ev, eu), w)
    W[np.diag_indices(n)] = 1.0 - W.sum(axis=1)
    return W


def spectral_E(n, eu, ev, T, eps, p_transient=0.0):
    if _n_components(n, eu, ev) > 1:
        return 1.0
    vals = np.linalg.eigvalsh(metropolis_W(n, eu, ev, 1.0 - p_transient))
    lam = np.abs(vals[:-1])                                 # drop the unit eigenvalue (largest)
    ms = max(float(np.sum(lam ** (2 * T)) / (n - 1)), 1e-300)
    return float(np.clip(1.0 - min(1.0, -0.5 * np.log(ms) / np.log(1.0 / eps)), 0.0, 1.0))


def laplacian_lambda2(n, eu, ev):
    L = np.zeros((n, n))
    L[eu, ev] = -1.0
    L[ev, eu] = -1.0
    L[np.diag_indices(n)] = -L.sum(axis=1)
    vals = np.linalg.eigvalsh(L)
    return float(max(vals[1], 0.0))


def E_from_lambda2(lam2, dmax, T, eps, q=1.0):
    rho = 1.0 - q * lam2 / (1.0 + dmax)
    if rho >= 1.0 - 1e-12 or lam2 <= 1e-12:
        return 1.0
    return float(np.clip(1.0 - min(1.0, T * (-np.log(max(rho, 1e-12))) / np.log(1.0 / eps)), 0.0, 1.0))


def laplacian_E(n, eu, ev, T, eps, p_transient=0.0):
    if _n_components(n, eu, ev) > 1:
        return 1.0
    dmax = int(np.max(np.bincount(eu, minlength=n) + np.bincount(ev, minlength=n)))
    return E_from_lambda2(laplacian_lambda2(n, eu, ev), dmax, T, eps, 1.0 - p_transient)


# ------------------------------------------------------------------ calibration map (isotonic regression, pool-adjacent-violators)
class CalibrationMap:
    """Monotone map predicted E -> realised E. Identity until fit() has >= min_n points."""

    def __init__(self, min_n=30):
        self.min_n, self.x, self.y = min_n, None, None

    def fit(self, pred, real):
        pred, real = np.asarray(pred, float), np.asarray(real, float)
        if len(pred) < self.min_n:
            return self
        o = np.argsort(pred, kind="mergesort")
        x, y = pred[o], real[o]
        vals, wts, lefts, rights = [], [], [], []
        for xi, yi in zip(x, y):                             # pool-adjacent-violators; each block keeps its left and right x
            vals.append(yi); wts.append(1.0); lefts.append(xi); rights.append(xi)
            while len(vals) > 1 and vals[-2] > vals[-1]:
                v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / (wts[-2] + wts[-1])
                w = wts[-2] + wts[-1]
                l0, r1 = lefts[-2], rights[-1]
                vals[-2:], wts[-2:], lefts[-2:], rights[-2:] = [v], [w], [l0], [r1]
        xs, ys = [], []
        for v, l, r in zip(vals, lefts, rights):             # a step inside each block, linear ramps between blocks
            xs += [l, r]; ys += [v, v]
        self.x, self.y = np.array(xs), np.array(ys)
        return self

    def __call__(self, e):
        return np.interp(e, self.x, self.y) if self.x is not None else e


# ------------------------------------------------------------------ gain estimator
@dataclass
class GainResult:
    G: np.ndarray              # (K,) expected gain to the end of the run, per candidate (null excluded)
    S_setup: np.ndarray
    b: np.ndarray
    G_imm: np.ndarray
    G_fut: np.ndarray
    G_s: np.ndarray            # (S, K) per-scenario gains (for standard errors and cross-fitting)
    se: np.ndarray             # (K,) standard error of G over scenarios


class GainEstimator:
    def __init__(self, n, eu, ev, T_rounds, eps, p_transient, d, H, mode="exact", calibration: CalibrationMap = None):
        assert mode in ("exact", "laplacian")
        self.n, self.eu, self.ev = n, np.asarray(eu), np.asarray(ev)
        self.T, self.eps, self.p_tr, self.d, self.H, self.mode = T_rounds, eps, p_transient, d, H, mode
        self.cal = calibration or CalibrationMap()

    def _E(self, mask, cache):
        key = mask.tobytes()
        v = cache.get(key)
        if v is None:
            idx = np.flatnonzero(mask)
            fn = spectral_E if self.mode == "exact" else laplacian_E
            v = float(self.cal(fn(self.n, self.eu[idx], self.ev[idx], self.T, self.eps, self.p_tr)))
            cache[key] = v
        return v

    def live_masks(self, configured, ready_at, k, down_sj, mutation):
        """Live masks of the null action or of `mutation` at epoch k+j for one scenario row: down_sj has shape (Hs, P)."""
        cfg, ready = configured.copy(), ready_at.copy()
        if mutation is not None:
            if mutation.remove is not None:
                cfg[mutation.remove] = False
            if mutation.add is not None:
                cfg[mutation.add] = True
                ready[mutation.add] = k + 1 + self.d
        epochs = k + 1 + np.arange(down_sj.shape[0])
        return cfg[None, :] & ~down_sj & (ready[None, :] <= epochs[:, None])

    def estimate(self, configured, ready_at, k, scen, candidates, tau_k, kappa=1.0) -> GainResult:
        Hs = self.d + self.H
        assert scen.H >= Hs, "scenario horizon must cover setup delay + benefit window"
        S, K = scen.S, len(candidates)
        cache = {}
        delta = np.zeros((S, Hs, K))
        for s in range(S):
            dn = scen.down[s, :Hs]
            null = self.live_masks(configured, ready_at, k, dn, None)
            e0 = np.array([self._E(null[j], cache) for j in range(Hs)])
            for c, a in enumerate(candidates):
                ma = self.live_masks(configured, ready_at, k, dn, a)
                delta[s, :, c] = e0 - np.array([self._E(ma[j], cache) for j in range(Hs)])
        setup = delta[:, :self.d, :].sum(axis=1)                         # (S, K) epochs k+1 .. k+d
        rate = delta[:, self.d:Hs, :].mean(axis=1)                       # (S, K) epochs k+d+1 .. k+d+H
        rem = max(0, tau_k - self.d)
        G_s = setup + kappa * rate * rem
        imm = setup + kappa * rate * min(1, rem)                         # H0 = d + 1  ->  one benefit epoch (if any remain)
        G = G_s.mean(axis=0)
        return GainResult(G=G, S_setup=setup.mean(axis=0), b=rate.mean(axis=0), G_imm=imm.mean(axis=0), G_fut=G - imm.mean(axis=0),
                          G_s=G_s, se=G_s.std(axis=0, ddof=1) / np.sqrt(S) if S > 1 else np.zeros(K))
