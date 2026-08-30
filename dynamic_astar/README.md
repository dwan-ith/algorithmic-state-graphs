# Dynamic A* (Lifelong Planning A*)

## 1. Incremental Heuristic Search

Implements LPA* over an undirected graph. Two values are maintained per node:
- $g(v)$: current best known start-cost,
- $rhs(v)$: one-step lookahead, $\min_{u \in pred(v)} (g(u) + w(u,v))$; $rhs(s) = 0$.

A node is *locally consistent* when $g(v) = rhs(v)$. The priority queue holds
only inconsistent nodes under the key
$$k(v) = \big(\min(g, rhs) + h(v),\ \min(g, rhs)\big).$$

## 2. Update Handling

An edge weight change makes only its two endpoints locally inconsistent;
`update_vertex` recomputes their `rhs` and the main loop re-expands just the
queue frontier needed to restore consistency up to the goal. Lazy deletion
keeps the heap correct without rebuilds.

The default heuristic is $h = 0$ (Dijkstra-equivalent), so no embedding is
required; supply an admissible heuristic by overriding `h()` for geometric
maps.

## 3. Measured behavior

`benchmark.py` (vs an independent O(V²) Dijkstra restart): ~90% of updates
trigger zero expansions; expansions per update average ~0.1–0.2 on random
workloads and 1.95 under adversarial tree-edge increases (speedup drops
from ~100–420x to ~49x — the LPA* bound degrades gracefully and honestly).
Validated by `tests/fuzz_oracle.py` against an independent Bellman-Ford
oracle.
