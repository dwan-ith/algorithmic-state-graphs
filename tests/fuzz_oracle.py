"""
Independent-oracle differential fuzzer for the ASG dynamic algorithms.

Every existing test in this repo validates a dynamic structure against the
SAME class rebuilt from scratch (e.g. DynamicPrim vs DynamicPrim).  A
deterministic bug that yields identical wrong output on both sides passes
such tests silently.  This harness validates against deliberately
*different* algorithms instead:

    MST / forest   -> Kruskal (sort + DSU)
    distances      -> Bellman-Ford
    max flow       -> dict-based Edmonds-Karp

so a shared deterministic defect cannot hide on both sides of the compare.

Covered operations per update: weight decrease, weight increase, edge
deletion (w=inf), edge re-insertion after deletion, brand-new edge
insertion -- over connected *and* disconnected graphs, including
tie-heavy weights that stress deterministic tie-breaking.

Usage:
    python tests/fuzz_oracle.py                       # quick smoke run
    python tests/fuzz_oracle.py --trials 300 --updates 60
    python tests/fuzz_oracle.py --algos prim,maxflow
"""

import argparse
import random
import sys
from collections import deque
from math import inf

sys.path.insert(0, ".")

from dynamic_prim.dynamic_prim import DynamicPrim
from dynamic_boruvka.dynamic_boruvka import DynamicBoruvka
from dynamic_kruskal.dynamic_kruskal import DynamicKruskal
from dynamic_dijkstra.dynamic_dijkstra import DynamicDijkstra
from dynamic_astar.dynamic_astar import DynamicAStar
from dynamic_maxflow.dynamic_maxflow import DynamicMaxFlow


# --------------------------------------------------------------------------
# Independent oracles (intentionally different algorithms/data structures)
# --------------------------------------------------------------------------

def oracle_mst_weights(n, edges):
    """Kruskal over finite edges -> sorted multiset of chosen edge weights.

    Every minimum spanning forest has exactly the same weight multiset, so
    this is a complete correctness invariant for MST/MSF outputs.
    """
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ws = []
    for (u, v), w in sorted(edges.items(), key=lambda kv: kv[1]):
        if w == inf:
            continue
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            ws.append(w)
    return sorted(ws)


def oracle_distances(n, edges, root):
    """Bellman-Ford (undirected) -> distance list; inf if unreachable."""
    d = [inf] * n
    if root >= n:
        return d
    d[root] = 0
    arcs = [(u, v, w) for (u, v), w in edges.items() if w != inf]
    for _ in range(n):
        changed = False
        for u, v, w in arcs:
            if d[u] + w < d[v]:
                d[v] = d[u] + w
                changed = True
            if d[v] + w < d[u]:
                d[u] = d[v] + w
                changed = True
        if not changed:
            break
    return d


def oracle_maxflow(n, edges, s, t):
    """Edmonds-Karp with an explicit per-direction capacity dict.

    residual(x, y) = cap(x, y) - f(x, y) + f(y, x)
    Handles antiparallel directed edges correctly.
    """
    cap = {k: v for k, v in edges.items() if 0 < v < inf and k[0] != k[1]}
    f = {}
    adj = {}
    for (u, v) in cap:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)

    def residual(x, y):
        return cap.get((x, y), 0) - f.get((x, y), 0) + f.get((y, x), 0)

    total = 0
    while True:
        par = {s: None}
        dq = deque([s])
        found = False
        while dq and not found:
            u = dq.popleft()
            for v in adj.get(u, []):
                if v not in par and residual(u, v) > 0:
                    par[v] = u
                    if v == t:
                        found = True
                        break
                    dq.append(v)
        if not found:
            return total
        b = inf
        v = t
        while par[v] is not None:
            u = par[v]
            b = min(b, residual(u, v))
            v = u
        v = t
        while par[v] is not None:
            u = par[v]
            if (u, v) in cap:
                f[(u, v)] = f.get((u, v), 0) + b
            else:
                f[(v, u)] = f[(v, u)] - b
            v = u
        total += b


# --------------------------------------------------------------------------
# Random graphs / update streams
# --------------------------------------------------------------------------

def random_graph(rng, n, p, max_w, connect):
    edges = {}
    nodes = list(range(n))
    rng.shuffle(nodes)
    if connect and n > 1:
        for i in range(1, n):
            u, v = nodes[i], nodes[rng.randrange(i)]
            edges[(min(u, v), max(u, v))] = rng.randint(1, max_w)
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) not in edges and rng.random() < p:
                edges[(i, j)] = rng.randint(1, max_w)
    # Optionally pre-delete edges so some runs start disconnected.
    if not connect and rng.random() < 0.5:
        finite = list(edges)
        for e in finite:
            if rng.random() < 0.25:
                edges[e] = inf
    return edges


def random_update(rng, n, edges, max_w):
    """Return (op_name, u, v, w_new) applying one random perturbation type."""
    finite = [k for k, w in edges.items() if w != inf]
    op = rng.choice(["dec", "inc", "del", "add"])
    if op == "dec" and finite:
        u, v = rng.choice(finite)
        w = edges[(u, v)]
        return op, u, v, max(1, w - rng.randint(1, max(1, w)))
    if op == "inc" and finite:
        u, v = rng.choice(finite)
        return op, u, v, edges[(u, v)] + rng.randint(1, max(1, max_w // 2))
    if op == "del" and finite:
        u, v = rng.choice(finite)
        return op, u, v, inf
    absent = [(i, j) for i in range(n) for j in range(i + 1, n)
              if edges.get((i, j), inf) == inf and i != j]
    if absent:
        u, v = rng.choice(absent)
        return "add", u, v, rng.randint(1, max_w)
    if finite:
        u, v = rng.choice(finite)
        w = edges[(u, v)]
        return "dec", u, v, max(1, w - rng.randint(1, max(1, w)))
    return None


# --------------------------------------------------------------------------
# Per-algorithm adapters: build instance from edge dict, check vs oracle
# --------------------------------------------------------------------------

def build_prim(n, edges):
    d = DynamicPrim(n)
    for (u, v), w in edges.items():
        if w != inf:
            d.add_edge(u, v, w)
    d.compute_initial()
    return d


def _components(n, arc_list):
    """Connected-component labels via DSU over undirected arcs."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in arc_list:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), set()).add(i)
    return set(frozenset(g) for g in groups.values())


def _check_tree_output(got, n, sub_edges, label):
    """Shared validation of a minimum spanning tree/forest output."""
    gw = sorted(w for _, _, w in got)
    ow = oracle_mst_weights(n, sub_edges)
    if gw != ow:
        return f"weight multiset mismatch dyn={gw} oracle={ow}"

    canon = [(min(u, p), max(u, p), w) for u, p, w in got]
    if len(canon) != len(set(canon)):
        return "duplicate MST edges"
    for u, v, w in canon:
        if sub_edges.get((u, v)) != w:
            return f"fabricated/changed edge ({u},{v},{w}) not in graph"

    tree_groups = _components(n, [(u, v) for u, v, _ in canon])
    expected = _components(n, [(u, v) for (u, v) in sub_edges])
    if tree_groups != expected:
        return (f"{label}: component structure mismatch:\n  tree : "
                f"{sorted(map(sorted, tree_groups))}\n  graph: "
                f"{sorted(map(sorted, expected))}")
    return None


def check_prim(dyn, n, edges):
    # DynamicPrim's contract: MST of the ROOT'S connected component only.
    root = getattr(dyn, "root", 0)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (u, v), w in edges.items():
        if w != inf:
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    root_comp = frozenset(i for i in range(n) if find(i) == find(root))
    sub_edges = {(u, v): w for (u, v), w in edges.items()
                 if w != inf and u in root_comp}

    return _check_tree_output(dyn.get_mst_edges(), n, sub_edges,
                              "prim/root-component")


def check_forest(dyn, n, edges):
    # Boruvka/Kruskal contract: a full minimum spanning FOREST.
    sub_edges = {(u, v): w for (u, v), w in edges.items() if w != inf}
    return _check_tree_output(dyn.get_mst_edges(), n, sub_edges, "forest")


def build_boruvka(n, edges):
    d = DynamicBoruvka(n)
    for (u, v), w in edges.items():
        if w != inf:
            d.add_edge(u, v, w)
    d.compute_initial()
    return d


check_boruvka = check_forest


def build_kruskal(n, edges):
    d = DynamicKruskal(n)
    for (u, v), w in edges.items():
        if w != inf:
            d.add_edge(u, v, w)
    d.compute_initial()
    return d


check_kruskal = check_forest


def build_dijkstra(n, edges):
    d = DynamicDijkstra(n)
    for (u, v), w in edges.items():
        if w != inf:
            d.add_edge(u, v, w)
    d.compute_initial()
    return d


def check_dijkstra(dyn, n, edges):
    got = dyn.get_distances()
    exp = oracle_distances(n, edges, dyn.root)
    if got != exp:
        bad = [(i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e][:5]
        return f"distances mismatch at {bad}"
    return None


def build_astar(n, edges):
    d = DynamicAStar(n, 0, n - 1)
    for (u, v), w in edges.items():
        if w != inf:
            d.add_edge(u, v, w)
    d.compute_initial()
    return d


def check_astar(dyn, n, edges):
    exp = oracle_distances(n, edges, 0)[n - 1]
    if dyn.g[n - 1] != exp:
        return f"g(goal)={dyn.g[n - 1]} oracle={exp}"
    return None


def build_maxflow(n, edges):
    d = DynamicMaxFlow(n, 0, n - 1)
    for (u, v), w in edges.items():
        if w > 0 and w != inf:
            d.add_edge(u, v, w)
    d.compute_initial()
    return d


def check_maxflow(dyn, n, edges):
    exp = oracle_maxflow(n, edges, 0, n - 1)
    if dyn.get_max_flow() != exp:
        return f"maxflow={dyn.get_max_flow()} oracle={exp}"
    return None


ALGOS = {
    "prim":     ("Dynamic Prim",     build_prim,     check_prim),
    "boruvka":  ("Dynamic Boruvka",  build_boruvka,  check_boruvka),
    "kruskal":  ("Dynamic Kruskal",  build_kruskal,  check_kruskal),
    "dijkstra": ("Dynamic Dijkstra", build_dijkstra, check_dijkstra),
    "astar":    ("Dynamic A*",       build_astar,    check_astar),
    "maxflow":  ("Dynamic MaxFlow",  build_maxflow,  check_maxflow),
}

FLOW_ONLY = {"maxflow"}


def dump_repro(name, trial, seed, n, init_edges, hist, fail_idx, detail,
               is_flow):
    lines = [f"REPRO [{name}] trial={trial} seed={seed} failed at update "
             f"{fail_idx}: {detail}",
             f"n = {n}" + (f", s=0, t={n-1}" if is_flow else ""),
             f"initial_edges = {init_edges!r}",
             f"history = {hist!r}"]
    text = "\n".join(lines)
    print(text)
    try:
        with open("tests/repro_failure.txt", "a", encoding="utf-8") as fh:
            fh.write(text + "\n\n")
    except OSError:
        pass


# --------------------------------------------------------------------------
# Main fuzz loop
# --------------------------------------------------------------------------

def fuzz(algo_key, trials, updates, max_n, base_seed, verbose):
    name, builder, checker = ALGOS[algo_key]
    is_flow = algo_key in FLOW_ONLY
    failures = 0
    for trial in range(trials):
        seed = base_seed + trial
        rng = random.Random(seed)
        n = rng.randint(2, max_n)
        tie_heavy = rng.random() < 0.4
        max_w = rng.choice([2, 3, 5]) if tie_heavy else 100
        connect = rng.random() < 0.7
        p = rng.choice([0.15, 0.3, 0.5])
        edges = random_graph(rng, n, p, max_w, connect)
        init_edges = dict(edges)

        dyn = builder(n, edges)

        hist = []
        for k in range(updates):
            upd = random_update(rng, n, edges, max_w)
            if upd is None:
                break
            op, u, v, w_new = upd
            hist.append((u, v, w_new))
            stored = 0 if (is_flow and w_new == inf) else w_new
            edges[(u, v)] = stored
            try:
                dyn.update_edge(u, v, stored)
            except Exception as ex:  # noqa: BLE001 - report crashes too
                dump_repro(name, trial, seed, n, init_edges, hist, k,
                           f"exception: {ex!r}", is_flow)
                failures += 1
                break
            detail = checker(dyn, n, edges)
            if detail is not None:
                dump_repro(name, trial, seed, n, init_edges, hist, k, detail,
                           is_flow)
                failures += 1
                break
        else:
            if verbose:
                print(f"  [{name}] trial {trial}: ok ({len(hist)} updates)")
            continue
    status = "PASS" if failures == 0 else f"{failures} FAILING TRIALS"
    print(f"[{name}] trials={trials} updates/trial<={updates} -> {status}")
    return failures


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--updates", type=int, default=50)
    ap.add_argument("--max-n", type=int, default=9)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--algos", type=str,
                    default="prim,boruvka,kruskal,dijkstra,astar,maxflow")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    total = 0
    for key in args.algos.split(","):
        total += fuzz(key.strip(), args.trials, args.updates, args.max_n,
                      args.seed, args.verbose)
    sys.exit(1 if total else 0)
