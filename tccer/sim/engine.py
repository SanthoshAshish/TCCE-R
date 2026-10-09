"""Simulation engine: one run = one (config, seed, policy). Implements the epoch loop.

Per epoch k:
  1. environment events (background failures/repairs, bursts)     -> (1) Dynamic Network State
  2. T consensus rounds with transient failures, fresh x(0)        -> (2) Consensus Monitor
  3. resilience metrics (lambda2, components, bridges, volatility)
  4. policy.decide: debt / trigger / evaluator / gate / selector   -> (3)-(7), (9)
  5. apply mutation; takes effect from epoch k+1                   -> (8) Reconfigured Network
"""
import networkx as nx
import numpy as np

from tccer.consensus.algorithm import run_epoch
from tccer.consensus.monitor import summarize
from tccer.core.debt import volatility
from tccer.core.selector import EMPTY_SELECTION, MutationPipeline
from tccer.metrics.resilience import lambda2, vulnerability
from tccer.network.events import FailureTrace
from tccer.network.generators import random_geometric
from tccer.network.state import NetworkState
from tccer.policies import POLICIES


def simulate(cfg, seed: int, policy_name: str, log_rounds: bool = True):
    pos, eu, ev, length, init_idx = random_geometric(cfg.n_nodes, cfg.init_radius, cfg.radio_range, seed)
    state = NetworkState(pos, eu, ev, length, init_idx)
    trace = FailureTrace(cfg, seed, state.P, edge_mid=(pos[eu] + pos[ev]) / 2)
    x0_all = np.random.default_rng([seed, 2]).random((cfg.epochs, cfg.n_nodes))
    pipeline = MutationPipeline(cfg, len(init_idx), state.P)
    policy = POLICIES[policy_name](cfg, pipeline, np.random.default_rng([seed, 3]))

    epoch_rows, round_rows, changes = [], [], []
    background_down = state.down.copy()          # background Markov state; bursts are layered on top
    for k in range(cfg.epochs):
        state.epoch = k
        # 1. environment
        background_down = trace.epoch_update(k, background_down)
        new_down = background_down | trace.burst[k]
        changes.append(int(((new_down != state.down) & state.configured).sum()))
        state.down = new_down

        # 2. consensus
        live = np.flatnonzero(state.live_mask())
        u, v = state.eu[live], state.ev[live]
        err = run_epoch(x0_all[k], u, v, lambda t: trace.transient_up(k, t)[live], cfg.rounds_per_epoch)
        rep = summarize(err, cfg.eps)

        # 3. resilience metrics
        g = state.graph()
        comps = nx.number_connected_components(g)
        obs = {
            "E_hat": rep.E_hat,
            "final_error": rep.final_error,
            "conv_round": rep.conv_round if rep.conv_round is not None else -1,
            "rate": rep.rate,
            "lambda2": lambda2(state.n, u, v) if comps == 1 else 0.0,
            "components": comps,
            "C": vulnerability(g),
            "V": volatility(changes, int(state.configured.sum()), cfg.vol_window),
            "live_edges": len(live),
            "configured_edges": int(state.configured.sum()),
            "pending_links": int((state.configured & (state.ready_at > k)).sum()),
            "n_down_potential": int(state.down.sum()),
            "n_burst_down": int(trace.burst[k].sum()),
            "budget": pipeline.budget,
            # logging only: could the shared selector+gate reconnect the network this epoch?
            "reconnect_possible": pipeline.can_reconnect(state, k) if comps > 1 else True,
        }

        # 4. policy
        pipeline.last = dict(EMPTY_SELECTION)
        m = policy.decide(k, obs, state)

        # 5. apply
        if m is not None:
            state.apply(m, cfg.link_setup_epochs)
            pipeline.commit(m, k)

        epoch_rows.append({"seed": seed, "policy": policy_name, "epoch": k, **obs, **policy.info(),
                           "mutation": m.describe(state) if m else "", "mutation_kind": m.kind() if m else "",
                           "n_mutations": policy.n_mutations, "gate_rejections": pipeline.gate.rejections,
                           **pipeline.last})
        if log_rounds:
            round_rows.extend({"seed": seed, "policy": policy_name, "epoch": k, "round": t, "error": e}
                              for t, e in enumerate(err))
    return epoch_rows, round_rows
