"""
Unified benchmark for all ASG dynamic-graph algorithm implementations.

Methodology notes (deliberately honest):
  * Correctness is checked per update against *independent reference*
    implementations (textbook Kruskal / heap-Prim / O(V^2) Dijkstra /
    dict Edmonds-Karp), NOT against the dynamic classes themselves.
  * Static baselines are those same lean references -- i.e. a cold restart
    with no state -- so reported speedups are "dynamic vs plain restart".
    They are NOT comparisons against state-of-the-art dynamic data
    structures (link-cut/topology trees, Holm-Thorup, etc.).
  * Modes:
      mixed            - random decreases / increases / deletions / insertions
      adversarial_mst  - always raises the lightest current tree edge
                         (forces replacement search almost every update);
                         flow benches interpret this as the tight/saturated
                         regime, A* falls back to pure increases
"""

import os
import sys
import time
import random
import heapq
import tracemalloc
from math import inf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Shared graph generator ──────────────────────────────────────────────────


def make_graph(n, edge_prob=0.08, max_w=100, seed=42):
    rng = random.Random(seed)
    edges = {}
    nodes = list(range(n))
    rng.shuffle(nodes)
    for i in range(1, n):          # spanning tree backbone
        u, v = nodes[i], nodes[rng.randint(0, i - 1)]
        u, v = min(u, v), max(u, v)
        edges[(u, v)] = rng.randint(1, max_w)
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < edge_prob:
                edges.setdefault((min(i, j), max(i, j)),
                                 rng.randint(1, max_w))
    return edges


def random_update(edges, n=None, mode='mixed', seed=None):
    """Return (u, v, w_new) for a perturbation; inf means delete."""
    rng = random.Random(seed) if seed is not None else random
    items = list(edges.items())
    (u, v), w = rng.choice(items)
    if mode == 'decrease':
        return u, v, max(1, w - rng.randint(1, max(1, w // 2)))
    if mode == 'increase':
        return u, v, w + rng.randint(1, 50)
    if mode == 'targeted_mst':
        return u, v, w + rng.randint(1, 30)
    op = rng.choice(['dec', 'inc', 'inc', 'del', 'add'])
    if op == 'dec':
        return u, v, max(1, w - rng.randint(1, max(1, w // 2)))
    if op == 'inc':
        return u, v, w + rng.randint(1, 50)
    if op == 'del':
        return u, v, inf
    if n is not None:
        for _ in range(64):
            a, b = rng.randrange(n), rng.randrange(n)
            if a != b and (min(a, b), max(a, b)) not in edges:
                return min(a, b), max(a, b), rng.randint(1, 100)
    return u, v, w + rng.randint(1, 50)


def add_edges(instance, edges_dict):
    for (u, v), w in edges_dict.items():
        if w != inf:
            instance.add_edge(u, v, w)


# ── Independent lean reference implementations ───────────────────────────────


def ref_kruskal_weight(n, edges_dict):
    """Textbook Kruskal: sort + DSU. Returns MSF weight."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total = 0
    for (u, v), w in sorted(edges_dict.items(), key=lambda kv: kv[1]):
        if w == inf:
            continue
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            total += w
    return total


def ref_prim_weight(n, edges_dict, root=0):
    """Textbook lazy Prim (root component only). Returns tree weight."""
    adj = [{} for _ in range(n)]
    for (u, v), w in edges_dict.items():
        if w != inf:
            adj[u][v] = w
            adj[v][u] = w
    seen = [False] * n
    pq = [(0, root)]
    total = 0
    while pq:
        w, u = heapq.heappop(pq)
        if seen[u]:
            continue
        seen[u] = True
        total += w
        for v, wt in adj[u].items():
            if not seen[v]:
                heapq.heappush(pq, (wt, v))
    return total


def ref_dijkstra(n, edges_dict, root=0):
    """O(V^2) scan Dijkstra. Returns distance list."""
    adj = [{} for _ in range(n)]
    for (u, v), w in edges_dict.items():
        if w != inf:
            adj[u][v] = w
            adj[v][u] = w
    dist = [inf] * n
    done = [False] * n
    dist[root] = 0
    for _ in range(n):
        best, bi = inf, -1
        for i in range(n):
            if not done[i] and dist[i] < best:
                best, bi = dist[i], i
        if bi == -1:
            break
        done[bi] = True
        for v, w in adj[bi].items():
            if dist[bi] + w < dist[v]:
                dist[v] = dist[bi] + w
    return dist


def ref_maxflow(n, edges_dict, s=0, t=None):
    """Dict-based Edmonds-Karp reference."""
    t = n - 1 if t is None else t
    cap = {k: v for k, v in edges_dict.items() if 0 < v < inf}
    adj = {}
    for (u, v) in cap:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    flow = {}

    def residual(x, y):
        return cap.get((x, y), 0) - flow.get((x, y), 0) + flow.get((y, x), 0)

    total = 0
    while True:
        par = {s: None}
        q = [s]
        found = False
        while q and not found:
            x = q.pop(0)
            for y in adj.get(x, []):
                if y not in par and residual(x, y) > 0:
                    par[y] = x
                    if y == t:
                        found = True
                        break
                    q.append(y)
        if not found:
            return total
        b, y = inf, t
        while par[y] is not None:
            b = min(b, residual(par[y], y))
            y = par[y]
        y = t
        while par[y] is not None:
            x = par[y]
            if (x, y) in cap:
                flow[(x, y)] = flow.get((x, y), 0) + b
            else:
                flow[(y, x)] = flow.get((y, x), 0) - b
            y = x
        total += b


# ── Per-algorithm benchmarks ────────────────────────────────────────────────


def bench_prim(n, n_updates, edge_prob, mode='mixed'):
    from dynamic_prim.dynamic_prim import DynamicPrim
    edges = make_graph(n, edge_prob)
    dyn = DynamicPrim(n)
    add_edges(dyn, edges)
    dyn.compute_initial()

    def truth(ed):
        return ref_prim_weight(n, ed)

    return _run_loop(dyn, edges, n, n_updates, mode,
                     truth,
                     lambda d: sum(w for _, _, w in d.get_mst_edges()),
                     stats_fn=lambda d: {
                         'fast_rate': d.fast_repairs,
                         'rebuilds': d.rebuilds_triggered,
                         'sens': d.affected_steps_total})


def bench_boruvka(n, n_updates, edge_prob, mode='mixed'):
    from dynamic_boruvka.dynamic_boruvka import DynamicBoruvka
    edges = make_graph(n, edge_prob)
    dyn = DynamicBoruvka(n)
    add_edges(dyn, edges)
    dyn.compute_initial()
    return _run_loop(dyn, edges, n, n_updates, mode,
                     lambda ed: ref_kruskal_weight(n, ed),
                     lambda d: sum(w for _, _, w in d.get_mst_edges()),
                     stats_fn=lambda d: {'fast_rate': d.fast_repairs,
                                         'rebuilds': d.rebuilds_triggered},
                     adversarial='mst')


def bench_kruskal(n, n_updates, edge_prob, mode='mixed'):
    from dynamic_kruskal.dynamic_kruskal import DynamicKruskal
    edges = make_graph(n, edge_prob)
    dyn = DynamicKruskal(n)
    add_edges(dyn, edges)
    dyn.compute_initial()
    return _run_loop(dyn, edges, n, n_updates, mode,
                     lambda ed: ref_kruskal_weight(n, ed),
                     lambda d: sum(w for _, _, w in d.get_mst_edges()),
                     stats_fn=lambda d: {'fast_rate': d.fast_repairs,
                                         'rebuilds': d.rebuilds},
                     adversarial='mst')


def _lightest_tree_edge_mst(dyn, n):
    """(u, v, w) of the lightest edge returned by get_mst_edges()."""
    got = dyn.get_mst_edges()
    return got[0] if got else None


def _pick_adversarial_mst(dyn, edges, n, jump=150):
    e = _lightest_tree_edge_mst(dyn, n)
    if e is None:
        return None
    u, v, w = e
    return u, v, w + jump


def _run_loop(dyn, edges, n, n_updates, mode, truth_fn, value_fn,
              stats_fn, adversarial=None):
    t_dyn = t_static = 0
    errors = 0
    fast_total = rebuild_total = sens_total = 0
    for i in range(n_updates):
        if mode == 'adversarial_mst' and adversarial == 'mst':
            upd = _pick_adversarial_mst(dyn, edges, n)
            if upd is None:
                upd = random_update(edges, n=n, mode='increase', seed=i)
        else:
            eff = mode if mode != 'adversarial_mst' else 'increase'
            upd = random_update(edges, n=n, mode=eff, seed=i)
        u, v, w_new = upd
        edges[(u, v)] = w_new

        t0 = time.perf_counter()
        dyn.update_edge(u, v, w_new)
        t_dyn += time.perf_counter() - t0

        t0 = time.perf_counter()
        expected = truth_fn(edges)
        t_static += time.perf_counter() - t0

        if value_fn(dyn) != expected:
            errors += 1
        st = stats_fn(dyn)
        fast_total = st['fast_rate']
        rebuild_total = st['rebuilds']
        sens_total = st.get('sens', 0)

    total = fast_total + rebuild_total
    r = {
        'errors': errors,
        'fast_rate': fast_total / total if total else 0,
        'speedup': t_static / t_dyn if t_dyn > 0 else float('inf'),
        't_dyn_ms': t_dyn * 1000,
        't_static_ms': t_static * 1000,
    }
    if sens_total:
        r['sensitivity'] = sens_total / (n * n_updates) if n_updates else 0
    return r


def bench_dijkstra(n, n_updates, edge_prob, mode='mixed'):
    from dynamic_dijkstra.dynamic_dijkstra import DynamicDijkstra
    edges = make_graph(n, edge_prob)
    dyn = DynamicDijkstra(n)
    add_edges(dyn, edges)
    dyn.compute_initial()

    t_dyn = t_static = 0
    errors = 0
    for i in range(n_updates):
        u, v, w_new = random_update(edges, n=n, mode=mode, seed=i)
        edges[(u, v)] = w_new

        t0 = time.perf_counter()
        dyn.update_edge(u, v, w_new)
        t_dyn += time.perf_counter() - t0

        t0 = time.perf_counter()
        expected = ref_dijkstra(n, edges)
        t_static += time.perf_counter() - t0

        if dyn.get_distances() != expected:
            errors += 1

    total = dyn.fast_repairs + dyn.rebuilds_triggered
    return {
        'errors': errors,
        'fast_rate': dyn.fast_repairs / total if total else 0,
        'sensitivity': dyn.affected_nodes_total / (n * n_updates)
                        if n_updates else 0,
        'speedup': t_static / t_dyn if t_dyn > 0 else float('inf'),
        't_dyn_ms': t_dyn * 1000,
        't_static_ms': t_static * 1000,
    }


def bench_astar(n, n_updates, edge_prob, mode='mixed'):
    from dynamic_astar.dynamic_astar import DynamicAStar
    edges = make_graph(n, edge_prob)
    dyn = DynamicAStar(n, 0, n - 1)
    add_edges(dyn, edges)
    dyn.compute_initial()

    t_dyn = t_static = 0
    errors = 0
    expansions_before = dyn.node_expansions
    for i in range(n_updates):
        eff = 'increase' if mode == 'adversarial_mst' else mode
        u, v, w_new = random_update(edges, n=n, mode=eff, seed=i)
        edges[(u, v)] = w_new

        t0 = time.perf_counter()
        dyn.update_edge(u, v, w_new)
        t_dyn += time.perf_counter() - t0

        t0 = time.perf_counter()
        expected = ref_dijkstra(n, edges)[n - 1]
        t_static += time.perf_counter() - t0

        if dyn.g[n - 1] != expected:
            errors += 1

    total = dyn.node_expansions - expansions_before
    return {
        'errors': errors,
        'fast_rate': dyn.fast_repairs / n_updates if n_updates else 0,
        'avg_expansions': total / n_updates if n_updates else 0,
        'speedup': t_static / t_dyn if t_dyn > 0 else float('inf'),
        't_dyn_ms': t_dyn * 1000,
        't_static_ms': t_static * 1000,
    }


def bench_maxflow(n, n_updates, edge_prob, mode='mixed'):
    from dynamic_maxflow.dynamic_maxflow import DynamicMaxFlow

    if mode == 'adversarial_mst':
        # Tight/saturated regime: a uniform-capacity spine caps the flow
        # value, so every spine edge runs saturated; capacity cuts below
        # the flow value violate feasibility almost every update.
        rng = random.Random(7)
        edges = {}
        K = 12
        for i in range(n - 1):
            edges[(i, i + 1)] = K
        for _ in range(n):
            u = rng.randint(0, n - 2)
            v = rng.randint(u + 1, n - 1)
            edges.setdefault((u, v), rng.randint(K // 2, K))
    else:
        rng = random.Random(42)
        edges = {}
        for i in range(n - 1):
            edges[(i, i + 1)] = rng.randint(5, 20)
        for _ in range(n):
            u = rng.randint(0, n - 2)
            v = rng.randint(u + 1, n - 1)
            edges[(u, v)] = edges.get((u, v), 0) + rng.randint(1, 15)

    dyn = DynamicMaxFlow(n, 0, n - 1)
    add_edges(dyn, edges)
    dyn.compute_initial()

    t_dyn = t_static = 0
    errors = 0
    for i in range(n_updates):
        if mode == 'adversarial_mst':
            # Violation-by-construction: cut capacity below the CURRENT
            # flow on an edge that actually carries flow.  This measures
            # the reroute/cancel/re-augment repair path head-on instead
            # of hoping a random generator produces violations.
            flowing = [(e, fv) for e, fv in dyn.flow.items()
                       if isinstance(e[0], int) and fv > 0]
            if flowing:
                (u, v), fv = random.Random(9000 + i).choice(flowing)
                new_cap = max(0, fv - random.Random(i + 3).randint(1, 6))
            else:
                items = list(edges.items())
                (u, v), cap = random.Random(9000 + i).choice(items)
                new_cap = max(0, cap - random.Random(i + 3).randint(1, 6))
        else:
            items = list(edges.items())
            (u, v), cap = random.Random(1000 + i).choice(items)
            op = ['inc', 'dec', 'del'][i % 3]
            if op == 'inc':
                new_cap = cap + random.Random(i).randint(1, 5)
            elif op == 'dec':
                new_cap = max(0, cap - random.Random(i).randint(1, 5))
            else:
                new_cap = 0
        edges[(u, v)] = new_cap

        t0 = time.perf_counter()
        dyn.update_edge(u, v, new_cap)
        t_dyn += time.perf_counter() - t0

        t0 = time.perf_counter()
        expected = ref_maxflow(n, edges)
        t_static += time.perf_counter() - t0

        if dyn.get_max_flow() != expected:
            errors += 1

    total = dyn.fast_repairs + dyn.augmentations
    return {
        'errors': errors,
        'fast_rate': dyn.fast_repairs / total if total else 0,
        'speedup': t_static / t_dyn if t_dyn > 0 else float('inf'),
        't_dyn_ms': t_dyn * 1000,
        't_static_ms': t_static * 1000,
    }


# ── Memory probe ────────────────────────────────────────────────────────────


def memory_probe(key, n, updates, seed=123):
    """Retained + peak extra memory while applying `updates` mixed changes."""
    from dynamic_prim.dynamic_prim import DynamicPrim
    from dynamic_boruvka.dynamic_boruvka import DynamicBoruvka
    from dynamic_kruskal.dynamic_kruskal import DynamicKruskal
    from dynamic_dijkstra.dynamic_dijkstra import DynamicDijkstra
    from dynamic_astar.dynamic_astar import DynamicAStar
    from dynamic_maxflow.dynamic_maxflow import DynamicMaxFlow
    cls = {'prim': DynamicPrim, 'boruvka': DynamicBoruvka,
           'kruskal': DynamicKruskal, 'dijkstra': DynamicDijkstra,
           'astar': lambda nn: DynamicAStar(nn, 0, nn - 1),
           'maxflow': lambda nn: DynamicMaxFlow(nn, 0, nn - 1)}[key]
    is_flow = key == 'maxflow'

    edges = make_graph(n, 0.05, seed=seed)
    dyn = cls(n)
    add_edges(dyn, edges)
    dyn.compute_initial()

    tracemalloc.start()
    _, base = tracemalloc.get_traced_memory()
    for i in range(updates):
        u, v, w_new = random_update(edges, n=n, mode='mixed', seed=i)
        stored = 0 if (is_flow and w_new == inf) else w_new
        edges[(u, v)] = stored
        dyn.update_edge(u, v, stored)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (cur - base) / 1024.0, (peak - base) / 1024.0


# ── Runner ──────────────────────────────────────────────────────────────────


def fmt(r):
    e = r['errors']
    ok = '[OK]' if e == 0 else f'[FAIL] {e} errors'
    parts = [f"  {ok}",
             f"  fast-repair: {r.get('fast_rate', 0) * 100:.0f}%",
             f"  speedup vs cold restart: {r.get('speedup', 0):.2f}x",
             f"  dyn: {r.get('t_dyn_ms', 0):.1f}ms  "
             f"static-ref: {r.get('t_static_ms', 0):.1f}ms"]
    if 'sensitivity' in r:
        parts.append(f"  sensitivity: {r['sensitivity'] * 100:.1f}% state"
                     f" changed")
    if 'avg_expansions' in r:
        parts.append(f"  avg expansions/update: {r['avg_expansions']:.2f}")
    return '\n'.join(parts)


CONFIGS = [
    (200, 100, 0.05, 'mixed',         'random sparse (dec/inc/del/add)'),
    (500, 50,  0.03, 'mixed',         'larger graph'),
    (300, 80,  0.04, 'adversarial_mst',
     'ADVERSARIAL: always raise lightest tree edge / tight flow'),
]

BENCHES = [
    ('Dynamic Prim',     bench_prim),
    ('Dynamic Boruvka',  bench_boruvka),
    ('Dynamic Kruskal',  bench_kruskal),
    ('Dynamic Dijkstra', bench_dijkstra),
    ('Dynamic A*',       bench_astar),
    ('Dynamic MaxFlow',  bench_maxflow),
]

MEM_KEYS = ['prim', 'boruvka', 'kruskal', 'dijkstra', 'astar', 'maxflow']


if __name__ == '__main__':
    for name, fn in BENCHES:
        print(f'\n{"=" * 62}')
        print(f' {name}')
        print(f'{"=" * 62}')
        for n_, upd_, ep_, mode_, label_ in CONFIGS:
            try:
                r = fn(n_, upd_, ep_, mode_)
                print(f'\n  [{label_}]  n={n_}, {upd_} updates')
                print(fmt(r))
            except Exception as ex:  # noqa: BLE001
                import traceback
                print(f'\n  [{label_}] CRASHED: {ex}')
                traceback.print_exc()

    print(f'\n{"=" * 62}')
    print(' Retained dynamic-state memory (tracemalloc, mixed updates)')
    print(f'{"=" * 62}')
    for key in MEM_KEYS:
        try:
            retained, peak = memory_probe(key, n=400, updates=200)
            print(f'  {key:<9s} retained {retained:8.1f} KB   '
                  f'peak {peak:8.1f} KB')
        except Exception as ex:  # noqa: BLE001
            print(f'  {key:<9s} CRASHED: {ex}')
