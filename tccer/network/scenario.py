"""Custom scenario input (v0.5): user-supplied topology, initial values and scripted failure events.

Enabled by the config key `scenario_file`. Without it the simulator generates everything from the seed
(v0.1-v0.4 behaviour, unchanged). File format (YAML):

    description: optional free text
    nodes:            [[x, y], ...]          # required, >= 2 nodes; positions are used for regions and plots
    potential_links:  [[u, v], ...]          # optional; default = all pairs closer than the config's radio_range
    initial_links:    [[u, v], ...]          # required; must be a subset of potential_links
    initial_values:   [x0, x1, ...]          # optional; one value per node, reused every epoch,
                      or [[...], [...], ...] #   or one list per epoch (exactly `epochs` lists)
    failure_events:                          # optional; applied at the START of the given epoch (0-based)
      - {epoch: 5, link: [u, v], action: fail}       # link down from epoch 5 ...
      - {epoch: 9, link: [u, v], action: recover}    # ... until epoch 9 (up again from epoch 9)
      - {epoch: 12, region: {center: [x, y], radius: r}, duration: 3}
                                             # every potential link whose midpoint lies within r of the
                                             # centre is down for epochs 12, 13, 14

Scripted failures are layered on top of the random processes (down = random OR scripted), so every
strategy faces the same scripted events. A scripted `recover` only ends a scripted `fail`; it does not
repair a link that the random processes have broken. For a purely scripted scenario set p_transient,
p_fail and burst_rate to 0 in the config.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import yaml

TOP_KEYS = {"description", "nodes", "potential_links", "initial_links", "initial_values", "failure_events"}
LINK_EVENT_KEYS = {"epoch", "link", "action"}
REGION_EVENT_KEYS = {"epoch", "region", "duration"}


class ScenarioError(ValueError):
    """Raised for any invalid scenario file; the message says what is wrong and where."""


@dataclass
class Scenario:
    path: str
    description: str
    pos: np.ndarray            # (n, 2)
    eu: np.ndarray             # potential links, u < v, sorted
    ev: np.ndarray
    length: np.ndarray
    init_idx: np.ndarray       # indices into the potential-link arrays
    initial_values: Optional[np.ndarray]   # (epochs, n) or None
    scripted_down: np.ndarray  # (epochs, n_potential) bool
    events: list               # normalised events, for logging / plots


def _err(path, msg):
    raise ScenarioError(f"Scenario file {path}: {msg}")


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x)


def _parse_link(path, where, item, n):
    if not (isinstance(item, (list, tuple)) and len(item) == 2 and all(isinstance(a, int) and not isinstance(a, bool)
                                                                        for a in item)):
        _err(path, f"{where}: a link must be a pair of node indices like [0, 3], got {item!r}")
    u, v = item
    for a in (u, v):
        if not 0 <= a < n:
            _err(path, f"{where}: node index {a} does not exist (valid indices are 0..{n - 1})")
    if u == v:
        _err(path, f"{where}: link [{u}, {v}] connects a node to itself")
    return (min(u, v), max(u, v))


def _parse_link_list(path, key, items, n):
    if not isinstance(items, list):
        _err(path, f"'{key}' must be a list of [u, v] pairs")
    seen = {}
    for i, item in enumerate(items):
        link = _parse_link(path, f"{key}[{i}]", item, n)
        if link in seen:
            _err(path, f"{key}[{i}]: link {list(link)} is listed twice (also at {key}[{seen[link]}])")
        seen[link] = i
    return list(seen)


def load_scenario(path: str, cfg) -> Scenario:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ScenarioError(f"Scenario file not found: {path}") from None
    except yaml.YAMLError as e:
        raise ScenarioError(f"Scenario file {path} is not valid YAML: {e}") from None
    if not isinstance(data, dict):
        _err(path, "must be a YAML mapping with keys such as 'nodes:' and 'initial_links:'")
    unknown = set(data) - TOP_KEYS
    if unknown:
        _err(path, f"unknown key(s) {sorted(unknown)}; allowed keys are {sorted(TOP_KEYS)}")
    for req in ("nodes", "initial_links"):
        if req not in data:
            _err(path, f"required key '{req}' is missing")

    # nodes
    nodes = data["nodes"]
    if not isinstance(nodes, list) or len(nodes) < 2:
        _err(path, "'nodes' must be a list of at least 2 [x, y] positions")
    for i, p in enumerate(nodes):
        if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(_is_num(c) for c in p)):
            _err(path, f"nodes[{i}]: expected a position [x, y] of two numbers, got {p!r}")
    pos = np.array(nodes, dtype=float)
    n = len(pos)

    # links
    if "potential_links" in data and data["potential_links"] is not None:
        potential = _parse_link_list(path, "potential_links", data["potential_links"], n)
    else:
        iu, ju = np.triu_indices(n, k=1)
        d = np.linalg.norm(pos[iu] - pos[ju], axis=1)
        potential = [(int(a), int(b)) for a, b in zip(iu[d <= cfg.radio_range], ju[d <= cfg.radio_range])]
    potential = sorted(potential)
    index = {l: i for i, l in enumerate(potential)}
    initial = _parse_link_list(path, "initial_links", data["initial_links"], n)
    if not initial:
        _err(path, "'initial_links' is empty; the network needs at least one link")
    missing = [list(l) for l in initial if l not in index]
    if missing:
        src = "potential_links" if "potential_links" in data else f"pairs within radio_range={cfg.radio_range}"
        _err(path, f"initial link(s) {missing} are not in {src}")
    eu = np.array([l[0] for l in potential], dtype=int)
    ev = np.array([l[1] for l in potential], dtype=int)
    length = np.linalg.norm(pos[eu] - pos[ev], axis=1)
    init_idx = np.array(sorted(index[l] for l in initial), dtype=int)

    # initial values
    x0 = None
    if data.get("initial_values") is not None:
        iv = data["initial_values"]
        if isinstance(iv, list) and iv and all(_is_num(v) for v in iv):
            if len(iv) != n:
                _err(path, f"'initial_values' has {len(iv)} values but there are {n} nodes")
            x0 = np.tile(np.array(iv, dtype=float), (cfg.epochs, 1))
        elif isinstance(iv, list) and iv and all(isinstance(r, list) for r in iv):
            if len(iv) != cfg.epochs:
                _err(path, f"'initial_values' has {len(iv)} per-epoch lists but the config has epochs={cfg.epochs}")
            for k, r in enumerate(iv):
                if len(r) != n or not all(_is_num(v) for v in r):
                    _err(path, f"initial_values[{k}] must contain exactly {n} numbers")
            x0 = np.array(iv, dtype=float)
        else:
            _err(path, "'initial_values' must be a list of numbers (one per node) or a list of such lists (one per epoch)")

    # failure events
    events = data.get("failure_events") or []
    if not isinstance(events, list):
        _err(path, "'failure_events' must be a list")
    scripted = np.zeros((cfg.epochs, len(potential)), dtype=bool)
    norm, link_events = [], {}
    for i, e in enumerate(events):
        where = f"failure_events[{i}]"
        if not isinstance(e, dict):
            _err(path, f"{where}: each event must be a mapping like {{epoch: 5, link: [0, 1], action: fail}}")
        if "link" in e and "region" in e:
            _err(path, f"{where}: give either 'link' or 'region', not both")
        ep = e.get("epoch")
        if not (isinstance(ep, int) and not isinstance(ep, bool)) or not 0 <= ep < cfg.epochs:
            _err(path, f"{where}: 'epoch' must be an integer from 0 to {cfg.epochs - 1} (config epochs={cfg.epochs}), got {ep!r}")
        if "link" in e:
            extra = set(e) - LINK_EVENT_KEYS
            if extra:
                _err(path, f"{where}: unknown key(s) {sorted(extra)} for a link event (allowed: epoch, link, action)")
            link = _parse_link(path, where, e["link"], n)
            if link not in index:
                _err(path, f"{where}: link {list(link)} is not a potential link, so it can never exist")
            if e.get("action") not in ("fail", "recover"):
                _err(path, f"{where}: 'action' must be 'fail' or 'recover', got {e.get('action')!r}")
            link_events.setdefault(link, []).append((ep, e["action"], i))
            norm.append({"epoch": ep, "type": "link", "link": link, "action": e["action"]})
        elif "region" in e:
            extra = set(e) - REGION_EVENT_KEYS
            if extra:
                _err(path, f"{where}: unknown key(s) {sorted(extra)} for a region event (allowed: epoch, region, duration)")
            r = e["region"]
            if not (isinstance(r, dict) and set(r) == {"center", "radius"}):
                _err(path, f"{where}: 'region' must be {{center: [x, y], radius: r}}")
            c = r["center"]
            if not (isinstance(c, (list, tuple)) and len(c) == 2 and all(_is_num(a) for a in c)):
                _err(path, f"{where}: region centre must be [x, y], got {c!r}")
            if not (_is_num(r["radius"]) and r["radius"] > 0):
                _err(path, f"{where}: region radius must be a positive number, got {r['radius']!r}")
            dur = e.get("duration")
            if not (isinstance(dur, int) and not isinstance(dur, bool)) or dur < 1:
                _err(path, f"{where}: 'duration' must be a whole number of epochs >= 1, got {dur!r}")
            mid = (pos[eu] + pos[ev]) / 2
            hit = np.linalg.norm(mid - np.array(c, dtype=float), axis=1) <= r["radius"]
            if not hit.any():
                _err(path, f"{where}: region centre {list(c)} radius {r['radius']} contains no link midpoint")
            scripted[ep:ep + dur, hit] = True
            norm.append({"epoch": ep, "type": "region", "center": tuple(c), "radius": r["radius"],
                         "duration": dur, "links": [potential[j] for j in np.flatnonzero(hit)]})
        else:
            _err(path, f"{where}: an event needs either 'link' (with 'action') or 'region' (with 'duration')")

    # link fail/recover sequences: no duplicates, no conflicts
    for link, evs in link_events.items():
        evs.sort()
        down_since = None
        for k, (ep, act, i) in enumerate(evs):
            if k and evs[k - 1][0] == ep:
                _err(path, f"failure_events[{evs[k - 1][2]}] and failure_events[{i}]: two events for link "
                           f"{list(link)} at the same epoch {ep}")
            if act == "fail":
                if down_since is not None:
                    _err(path, f"failure_events[{i}]: link {list(link)} fails at epoch {ep} but is already failed "
                               f"since epoch {down_since} (add a 'recover' event in between)")
                down_since = ep
            else:
                if down_since is None:
                    _err(path, f"failure_events[{i}]: link {list(link)} recovers at epoch {ep} without an earlier "
                               f"scripted 'fail'")
                scripted[down_since:ep, index[link]] = True
                down_since = None
        if down_since is not None:
            scripted[down_since:, index[link]] = True

    return Scenario(path=path, description=str(data.get("description", "")), pos=pos, eu=eu, ev=ev,
                    length=length, init_idx=init_idx, initial_values=x0, scripted_down=scripted,
                    events=sorted(norm, key=lambda d: d["epoch"]))
