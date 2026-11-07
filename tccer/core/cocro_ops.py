"""COCRO v2: array-based candidate generation shared by the real decision (top-K_r removals x top-K_a additions) and the rollout base
policy (single best action on a scenario graph). Same semantics as tccer/core/mutations.py (strict budget, degree rule, tabu, failed-link
valuation 'zero' / 'if_up'), but operating on arrays so that it can be applied to simulated scenario graphs. [PROPOSED; design 2.4, 2.7]
The real actions are always re-checked by the unchanged SafetyGate in the policy; nothing here bypasses it."""
from dataclasses import dataclass

import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from tccer.metrics.resilience import lambda2_fiedler


@dataclass
class Rules:
    d_max: int | None          # None: no degree rule
    degree_basis: str          # "configured" or "live"
    failed_link_value: str     # "zero" or "if_up"
    strict_budget: bool        # budget_on == "configured": configured count is what the budget limits


def analyze_live(n, eu, ev, live):
    """Components, bridges and the Fiedler vector (None unless connected) of the live graph."""
    idx = np.flatnonzero(live)
    A = csr_matrix((np.ones(len(idx)), (eu[idx], ev[idx])), shape=(n, n))
    ncomp, label = connected_components(A, directed=False)
    bridges, fied = np.zeros(len(eu), dtype=bool), None            # bridges: boolean over potential links (live bridge links only)
    if ncomp == 1:
        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(zip(eu[idx].tolist(), ev[idx].tolist()))
        pairs = {tuple(sorted(e)) for e in nx.bridges(g)}
        if pairs:
            bridges[[i for i in idx.tolist() if (int(eu[i]), int(ev[i])) in pairs]] = True
        fied = lambda2_fiedler(n, eu[idx], ev[idx])[1]
    return ncomp, label, bridges, fied


def analyze_live_cached(cache, n, eu, ev, live):
    """analyze_live memoised on the live mask (a pure function of it for a fixed network; the cache is owned by one network's pricer)."""
    if cache is None:
        return analyze_live(n, eu, ev, live)
    key = live.tobytes()
    r = cache.get(key)
    if r is None:
        if len(cache) > 200_000:
            cache.clear()
        r = cache[key] = analyze_live(n, eu, ev, live)
    return r


def _deg(n, eu, ev, mask):
    return np.bincount(eu[mask], minlength=n) + np.bincount(ev[mask], minlength=n)


def rank_additions(n, eu, ev, length, configured, live, down, tabu, ana, top, removed=None, rules: Rules = None):
    """Indices of up to `top` addable links, best first: merge components first, then largest first-order lambda2 gain, then shortest."""
    ncomp, label, _, fied = ana
    addable = np.flatnonzero(~configured & ~down & ~tabu)
    if len(addable) == 0:
        return addable
    if rules is not None and rules.d_max is not None:
        mask = configured if rules.degree_basis == "configured" else live
        deg = _deg(n, eu, ev, mask)
        if removed is not None and mask[removed]:
            deg[eu[removed]] -= 1
            deg[ev[removed]] -= 1
        addable = addable[(deg[eu[addable]] < rules.d_max) & (deg[ev[addable]] < rules.d_max)]
        if len(addable) == 0:
            return addable
    merge = (label[eu[addable]] != label[ev[addable]]).astype(int)
    gain = (fied[eu[addable]] - fied[ev[addable]]) ** 2 if fied is not None else np.zeros(len(addable))
    order = np.lexsort((length[addable], -gain, -merge))
    return addable[order][:top]


def rank_removals(n, eu, ev, configured, live, down, tabu, ana, top, rules: Rules):
    """Up to `top` removable configured links, cheapest first. Live links must not be bridges and need a Fiedler vector; failed links are
    always removable. Loss: first-order lambda2 loss (failed links: 0 if failed_link_value == 'zero' or no Fiedler vector).
    Vectorised; same candidates, losses and stable ordering as the loop it replaced."""
    ncomp, label, bridges, fied = ana
    cand = np.flatnonzero(configured & ~tabu)
    failed = ~live[cand]
    ok = failed | ((fied is not None) & ~bridges[cand])
    cand, failed = cand[ok], failed[ok]
    if len(cand) == 0:
        return [], []
    if fied is None:
        loss = np.zeros(len(cand))
    else:
        loss = (fied[eu[cand]] - fied[ev[cand]]) ** 2
        if rules.failed_link_value == "zero":
            loss = np.where(failed, 0.0, loss)
    order = np.argsort(loss, kind="stable")[:top]
    return cand[order].tolist(), loss[order].tolist()


def candidate_pairs(n, eu, ev, length, configured, live, down, tabu, budget, rules: Rules, Kr, Ka, ana_cache=None):
    """List of (add, remove) with remove None when the budget is not full. Up to Kr removals x Ka additions (degree-feasible per removal)."""
    ana = analyze_live_cached(ana_cache, n, eu, ev, live)
    count = int(configured.sum()) if rules.strict_budget else int(live.sum())
    if count < budget:
        return [(int(a), None) for a in rank_additions(n, eu, ev, length, configured, live, down, tabu, ana, Ka, None, rules)]
    rem = rank_removals(n, eu, ev, configured, live, down, tabu, ana, Kr, rules)
    if not rem[0]:
        return []
    out = []
    for r in rem[0]:
        for a in rank_additions(n, eu, ev, length, configured, live, down, tabu, ana, Ka, r, rules):
            out.append((int(a), int(r)))
    return out
