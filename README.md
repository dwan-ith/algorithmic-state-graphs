# Algorithmic State Graphs

A collection of incremental graph algorithm implementations that make the **internal execution state of classical algorithms persistent** across graph changes, deriving repairs from invalidated local certificates rather than full recomputation.

## Core

Conventional algorithms compute $G \xrightarrow{A} S$ and discard the computational history on return. When the graph mutates ($G \rightarrow G'$), they restart from scratch.

Instead, we treat each algorithm's execution as a **persistent stateful object** — capturing its decision trace, local consistency certificates, and dependency links — and repair only the portion invalidated by a graph change:

$$T_{\text{dynamic}} = O(|\Delta G| + |\text{Affected}| + \text{overhead})$$

This idea appears across multiple well-studied problem domains. Ramalingam and Reps formalized it as **incremental computation** for shortest paths [[1]](https://www.microsoft.com/en-us/research/publication/incremental-algorithm-generalization-shortest-path-problem/). Likhachev et al. instantiated it in heuristic search as **LPA\*** and **D\* Lite** [[2]](https://www.sciencedirect.com/science/article/pii/S000437020300225X). Holm et al. applied hierarchical certificate structures to **dynamic MST** [[3]](https://dl.acm.org/doi/10.1145/502090.502095). This repository applies the same discipline uniformly across a broader set of greedy and flow algorithms.

## Implementations

| Algorithm | Certificate | Repair strategy on violation |
|-----------|-------------|------------------------------|
| [Dynamic Prim](dynamic_prim/) | Each extracted node achieves the global cut minimum at its step | Roll back to first preempted extraction slot, replay suffix |
| [Dynamic Borůvka](dynamic_boruvka/) | Cheapest outgoing edge per component per round | Truncate to first invalidated round, re-merge forward |
| [Dynamic Dijkstra](dynamic_dijkstra/) | $d[v] \le d[u] + w(u,v)$ for all edges | Forward relaxation / subtree invalidation + boundary re-seeding |
| [Dynamic Kruskal](dynamic_kruskal/) | Edge accepted iff endpoints are in distinct components at rank | Re-run Kruskal suffix from earliest shifted rank |
| [Dynamic A* (LPA*)](dynamic_astar/) | $g(v) = rhs(v)$ local consistency | Targeted re-expansion of inconsistent vertices |
| [Dynamic Max Flow](dynamic_maxflow/) | No augmenting path in residual; all capacity bounds satisfied | Reroute excess → cancel s–t flow → re-augment |

Every implementation exposes one uniform mutation API:

```python
dyn.add_edge(u, v, w)        # bulk load before compute_initial()
dyn.compute_initial()
dyn.update_edge(u, v, w)     # single edge-weight update
```

`update_edge` handles all four perturbation kinds:
weight **decrease**, weight **increase**, edge **deletion**
(`w = inf`, or `capacity = 0` for max-flow), and **insertion** of a
brand-new edge (any previously unseen pair).

## Measured results

Reproduce with `python benchmark.py` (Python 3.13, Windows). Baselines are
*independent lean references* (textbook Kruskal / heap-Prim / O(V²)
Dijkstra / dict Edmonds-Karp), i.e. a cold restart with no state — NOT
state-of-the-art dynamic data structures:

| Algorithm | Fast-repair | Speedup vs cold restart | Under adversarial load |
|-----------|-------------|--------------------------|------------------------|
| Dynamic Prim | 76–86% | 17–23x | 89% / 38x |
| Dynamic Borůvka | 77–86% | 1.3–1.7x | 0% / 0.54x (slower!) |
| Dynamic Kruskal | 82–92% | 4.4–9.1x | 0% / 2.3x |
| Dynamic Dijkstra | ~80% | 300–1327x | 88% / 211x |
| Dynamic A* (LPA*) | 90% | 100–417x | 94% / 49x (1.95 exp/upd) |
| Dynamic Max Flow | 96% | 11–110x | 89% / 3.2x |

The adversarial column is the honest stress case (`adversarial_mst`
config): MST rows always raise the lightest current tree edge, max-flow
cuts capacities below current flow on carrying edges every update. It
exposes exactly what the structure of each base algorithm implies:
globally ordered state (Borůvka/Kruskal rounds, sorted edge list) cannot
be maintained incrementally under targeted attacks, while locally
certificated state (Dijkstra subtree, LPA* consistency) absorbs them.

Retained dynamic-state memory at n=400 (tracemalloc, 200 mixed updates):
125–235 KB across modules; see the memory probe section of
`benchmark.py`.

## Correctness methodology

Two independent layers:

1. **Per-algorithm suites** (`python dynamic_<x>/test_dynamic_<x>.py`) —
   validate every update against a from-scratch recomputation.
2. **Independent-oracle fuzzer** (`python tests/fuzz_oracle.py`) —
   validates against deliberately *different* algorithms (Kruskal+DSU for
   MST, Bellman-Ford for distances, dict-based Edmonds-Karp for flow), so a
   deterministic defect cannot hide on both sides of a self-comparison.
   Covers weight changes, deletions, insertions, disconnected graphs and
   tie-heavy weights:

```
python tests/fuzz_oracle.py --trials 400 --updates 100 --max-n 12
```

## Known limitations (honest complexity notes)

* **Prim**: a suffix replay re-derives frontier keys by scanning the
  surviving prefix boundary — worst-case $O(V+E)$ per *rebuild*. Sub-linear
  rebuilds require either per-step frontier snapshots ($O(V)$ memory each)
  or a rollback-capable decrease-key queue; Python's `heapq` offers
  neither, so this is a deliberate tradeoff. Fast repairs (~80% of
  updates) avoid replay entirely.
* **Borůvka/Kruskal are structurally order-sensitive.** Their certificates
  live in global merge/sort order, so targeted increases on tree edges
  invalidate nearly every round (see adversarial column: 0% fast repairs,
  and Borůvka can be *slower* than recomputation). For truly adversarial
  fully-dynamic MST workloads, link-cut/topology-tree structures
  (Holm–de Lichtenberg–Thorup, Frederickson) are the right tools; these
  modules win on localized random workloads instead.
* Kruskal's fast paths cost $O(n\,\alpha)$ (prefix DSU over accepted edges
  plus one list scan); rebuilds replay a suffix of the sorted list.
* Dijkstra/A\* bounds are the provable Ramalingam–Reps / LPA* ones:
  update time proportional to affected vertices/edges only.
* Max-flow: feasibility-violation repairs route excess through residual /
  flow-carrying paths; cost scales with that search, not with $|V|$.
* Graphs are undirected for MST/shortest-path modules; max-flow is directed.
* Batched updates are applied one edge at a time.

## Related Work

1. Ramalingam & Reps — [*An Incremental Algorithm for a Generalization of the Shortest-Path Problem*](https://www.microsoft.com/en-us/research/publication/incremental-algorithm-generalization-shortest-path-problem/) (1996)
2. Likhachev et al. — [*Lifelong Planning A\**](https://www.sciencedirect.com/science/article/pii/S000437020300225X) (2004)
3. Holm, de Lichtenberg & Thorup — [*Poly-logarithmic Deterministic Fully-Dynamic Algorithms for Connectivity, MST, 2-Edge, and Biconnectivity*](https://dl.acm.org/doi/10.1145/502090.502095) (2001)
4. Frederickson — [*Data Structures for On-Line Updating of Minimum Spanning Trees*](https://epubs.siam.org/doi/10.1137/0214055) (1985)
