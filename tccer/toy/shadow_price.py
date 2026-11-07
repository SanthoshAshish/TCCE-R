"""COCRO v2 toy study: shadow price of a mutation unit — exact DP vs Monte-Carlo rollout vs the old i.i.d. method.
No simulator is involved; the model is a finite-horizon budgeted stopping problem with persistent-flow rewards.

Model (docs/COCRO_DESIGN.md sections 0, 2.3, 2.4):
  slots t = 0..T-1 (epochs); a Markov chain z_t (damage/opportunity level) with transition P = rho*I + (1-rho)*1 pi^T (stationary pi,
  persistence rho); acting at slot t with m units left (u = M - m already used) gives the reward
        R(t, z, u) = delta^u * b[z] * (T - t - d) - s*d - c_op      (benefit rate b[z] lasts to the end; setup loss s per epoch for d epochs;
                                                                  diminishing returns delta <= 1 on the benefit part)
  and requires cooldown: after acting the next slot cannot act (cd = 1), i.e. actions are >= 2 slots apart. T - t - d > 0 is required.
Methods compared:
  EXACT   backward-induction value V(t,m,z,cd); exact price  Lambda*(t,m,z) = E[V(t+1,m,z',0)] - E[V(t+1,m-1,z',1)]; act iff R >= Lambda*.
  ROLLOUT price from Monte-Carlo rollouts of the greedy base policy (act whenever R > 0) from the same state, common random numbers:
          Lambda_roll = E[W_base(wait)] - E[W_base(act then continue)];  act iff R >= Lambda_roll   (one-step policy improvement).
  IID     dynamic programme that treats the next slot's state as an independent draw from the stationary distribution (persistent-flow rewards).
  OLD     the v1 method: time-invariant truncated one-shot gain g(z) = b[z]*(H - d) - s*d - c_op, i.i.d. states, no diminishing returns.
  GREEDY  base policy; FRONT  state-blind: act whenever feasible (A7-like).

PRE-DECLARED PASS CRITERIA (fixed before the study was run; the study reports pass/fail for each, nothing is tuned afterwards):
  C1  the vectorised DP equals an explicit expectimax tree search on tiny instances (|diff| < 1e-9);
  C2  policy improvement: in EVERY configuration, value(ROLLOUT policy) >= value(GREEDY) - 2 SE (paired episodes);
  C3  near-optimality: mean over configurations of value(ROLLOUT)/value(EXACT) >= 0.95;
  C4  over-deferral of the i.i.d. method: in configurations with rho >= 0.9 and delta = 1 the mean deferral rate of IID exceeds that of EXACT by > 0.02,
      and value(IID) <= value(ROLLOUT) on average there; and at rho = 0 IID equals EXACT (price difference < 1e-9);
  C5  decision agreement: ROLLOUT agrees with EXACT's act/wait on >= 90% of non-marginal states (|R - Lambda*| > 0.05 * max(1, |Lambda*|)),
      pooled over configurations.
The study 'passes' iff C1-C5 all hold.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ToyConfig:
    T: int = 40
    M: int = 3
    d: int = 2                  # setup delay
    rho: float = 0.9            # persistence of the opportunity chain
    delta: float = 1.0          # diminishing returns on the benefit part
    s: float = 0.03             # setup loss per epoch
    c_op: float = 0.0
    H_old: int = 5              # window of the v1 truncated gain
    b: tuple = (0.0, 0.01, 0.03, 0.08, 0.20)
    pi: tuple = (0.50, 0.25, 0.15, 0.07, 0.03)

    @property
    def Z(self):
        return len(self.b)

    def P(self):
        pi = np.array(self.pi)
        return self.rho * np.eye(self.Z) + (1 - self.rho) * np.ones((self.Z, 1)) * pi[None, :]

    def reward(self, t, z, u):
        """Net reward of acting at slot t in state z with u units already used (vectorised in z and u)."""
        rem = self.T - t - self.d
        return (self.delta ** u) * np.asarray(self.b)[z] * rem - self.s * self.d - self.c_op


def feasible(cfg, t, m, cd):
    return (m > 0) & (cd == 0) & (cfg.T - t - cfg.d > 0)


# ---------------------------------------------------------------- exact DP
def solve_exact(cfg: ToyConfig):
    """V[t, m, z, cd] for t = 0..T (V[T] = 0), cd in {0, 1}; and the exact price Lambda*[t, m, z] (cd = 0)."""
    T, M, Z = cfg.T, cfg.M, cfg.Z
    P = cfg.P()
    V = np.zeros((T + 1, M + 1, Z, 2))
    for t in range(T - 1, -1, -1):
        for m in range(M + 1):
            for cd in (0, 1):
                wait = P @ V[t + 1, m, :, 0]                      # the cooldown is over at the next slot either way
                val = wait.copy()
                if m > 0 and cd == 0 and T - t - cfg.d > 0:
                    r = cfg.reward(t, np.arange(Z), M - m)
                    act = r + P @ V[t + 1, m - 1, :, 1]
                    val = np.maximum(wait, act)
                V[t, m, :, cd] = val
    lam = np.full((T, M + 1, Z), np.nan)
    for t in range(T):
        for m in range(1, M + 1):
            lam[t, m] = P @ V[t + 1, m, :, 0] - P @ V[t + 1, m - 1, :, 1]
    return V, lam


def expectimax(cfg: ToyConfig, t, m, z, cd):
    """Explicit recursive expectimax over the full tree (no memoisation): the independent check of solve_exact on tiny instances."""
    if t >= cfg.T:
        return 0.0
    P = cfg.P()

    def cont(m2, cd2):
        return sum(P[z, z2] * expectimax(cfg, t + 1, m2, z2, cd2) for z2 in range(cfg.Z))

    best = cont(m, 0)
    if m > 0 and cd == 0 and cfg.T - t - cfg.d > 0:
        best = max(best, float(cfg.reward(t, z, cfg.M - m)) + cont(m - 1, 1))
    return best


# ---------------------------------------------------------------- i.i.d. DP (persistent-flow rewards) and the v1 method
def solve_iid(cfg: ToyConfig):
    """Next states treated as independent stationary draws. W[t, m]; price Lambda_iid[t, m] = W[t+1, m] - W[t+2, m-1] (cooldown jump)."""
    T, M = cfg.T, cfg.M
    pi = np.array(cfg.pi)
    W = np.zeros((T + 3, M + 1))
    for t in range(T - 1, -1, -1):
        for m in range(M + 1):
            w = W[t + 1, m]
            if m > 0 and T - t - cfg.d > 0:
                r = cfg.reward(t, np.arange(cfg.Z), M - m)
                w = float(pi @ np.maximum(r + W[t + 2, m - 1], W[t + 1, m]))
            W[t, m] = w
    lam = np.full((T, M + 1), np.nan)
    for t in range(T):
        for m in range(1, M + 1):
            lam[t, m] = W[t + 1, m] - W[t + 2, m - 1]
    return W, lam


def solve_old(cfg: ToyConfig):
    """v1: time-invariant truncated one-shot gain, i.i.d. states, no diminishing returns. Returns (g[z], price[t, m])."""
    T, M = cfg.T, cfg.M
    pi = np.array(cfg.pi)
    g = np.asarray(cfg.b) * (cfg.H_old - cfg.d) - cfg.s * cfg.d - cfg.c_op
    W = np.zeros((T + 3, M + 1))
    for t in range(T - 1, -1, -1):
        for m in range(1, M + 1):
            W[t, m] = float(pi @ np.maximum(g + W[t + 2, m - 1], W[t + 1, m]))
    lam = np.full((T, M + 1), np.nan)
    for t in range(T):
        for m in range(1, M + 1):
            lam[t, m] = W[t + 1, m] - W[t + 2, m - 1]
    return g, lam


# ---------------------------------------------------------------- Monte-Carlo rollout price
def _next_state(cum_rows, u):
    return np.minimum((cum_rows < u[:, None]).sum(axis=1), cum_rows.shape[1] - 1)


def run_base(cfg: ToyConfig, t0, z, m, cd, U):
    """Greedy base policy (act iff feasible and R > 0) from slot t0 with per-rollout states z, units m, cooldown cd.
    U[:, t] are the uniforms driving the transition into slot t (common random numbers). Returns total reward per rollout."""
    cum = np.cumsum(cfg.P(), axis=1)
    z = z.copy()
    m = np.full(len(z), m) if np.isscalar(m) else m.copy()
    cd = np.full(len(z), cd) if np.isscalar(cd) else cd.copy()
    tot = np.zeros(len(z))
    for t in range(t0, cfg.T):
        if t > t0:
            z = _next_state(cum[z], U[:, t])
        r = cfg.reward(t, z, cfg.M - m)
        act = feasible(cfg, t, m, cd) & (r > 0)
        tot += np.where(act, r, 0.0)
        m = m - act
        cd = np.where(act, 1, 0)
    return tot


def rollout_price_table(cfg: ToyConfig, S=2000, seed=0):
    """Lambda_roll[t, m, z] for cd = 0 (NaN where acting is infeasible). Both branches share the same sampled next states and uniforms."""
    rng = np.random.default_rng(seed)
    cum = np.cumsum(cfg.P(), axis=1)
    U = rng.random((S, cfg.T + 1))
    lam = np.full((cfg.T, cfg.M + 1, cfg.Z), np.nan)
    for t in range(cfg.T):
        if cfg.T - t - cfg.d <= 0 or t + 1 >= cfg.T:
            continue
        for z0 in range(cfg.Z):
            z1 = _next_state(np.tile(cum[z0], (S, 1)), U[:, t + 1])
            for m in range(1, cfg.M + 1):
                lam[t, m, z0] = float(np.mean(run_base(cfg, t + 1, z1, m, 0, U) - run_base(cfg, t + 1, z1, m - 1, 1, U)))
    return lam


# ---------------------------------------------------------------- policy simulation on common episodes
def simulate_paths(cfg: ToyConfig, N=4000, seed=123):
    rng = np.random.default_rng(seed)
    cum = np.cumsum(cfg.P(), axis=1)
    pi_cum = np.cumsum(np.array(cfg.pi))
    z = np.empty((N, cfg.T), dtype=int)
    z[:, 0] = np.minimum((pi_cum[None, :] < rng.random(N)[:, None]).sum(axis=1), cfg.Z - 1)
    for t in range(1, cfg.T):
        z[:, t] = _next_state(cum[z[:, t - 1]], rng.random(N))
    return z


def evaluate_policy(cfg: ToyConfig, paths, decide):
    """decide(t, m_array, z_array) -> bool array 'act if feasible'. Returns per-episode totals, act counts and the deferral rate
    (share of feasible slot visits with R > 0 at which the policy waits)."""
    N = paths.shape[0]
    m = np.full(N, cfg.M)
    cd = np.zeros(N, dtype=int)
    tot = np.zeros(N)
    n_act = np.zeros(N)
    pos_visits = defer = 0
    for t in range(cfg.T):
        z = paths[:, t]
        feas = feasible(cfg, t, m, cd)
        r = cfg.reward(t, z, cfg.M - m)
        want = np.asarray(decide(t, m, z), dtype=bool) & feas
        pos = feas & (r > 0)
        pos_visits += int(pos.sum())
        defer += int((pos & ~want).sum())
        tot += np.where(want, r, 0.0)
        n_act += want
        m = m - want
        cd = np.where(want, 1, 0)
    return tot, n_act, (defer / max(1, pos_visits))


def policies(cfg: ToyConfig, rollout_seed=7, S=2000):
    V, lam_ex = solve_exact(cfg)
    _, lam_iid = solve_iid(cfg)
    g_old, lam_old = solve_old(cfg)
    lam_roll = rollout_price_table(cfg, S=S, seed=rollout_seed)

    def by_price(table3):
        return lambda t, m, z: cfg.reward(t, z, cfg.M - m) >= table3[t, np.maximum(m, 1), z]

    def by_price2(table2, truncated=False):
        def f(t, m, z):
            val = g_old[z] if truncated else cfg.reward(t, z, cfg.M - m)
            return val >= table2[t, np.maximum(m, 1)]
        return f

    pol = {"EXACT": by_price(lam_ex), "ROLLOUT": by_price(lam_roll), "IID": by_price2(lam_iid),
           "OLD": by_price2(lam_old, truncated=True),
           "GREEDY": lambda t, m, z: cfg.reward(t, z, cfg.M - m) > 0,
           "FRONT": lambda t, m, z: np.ones(len(z), dtype=bool)}
    return pol, dict(exact=lam_ex, roll=lam_roll, iid=lam_iid, old=lam_old, V=V)
