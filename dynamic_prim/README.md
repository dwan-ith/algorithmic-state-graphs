# Dynamic Prim's Algorithm

## 1. The Persistent Algorithmic State

The internal state is not merely the final tree, but the execution trace itself:
- $S_t$: the prefix set of vertices incorporated at chronological extraction step $t$,
- $\text{trace}_t[v]$: the cached cut weight at which each vertex was extracted,
- parent links recording which tree edge won at that step.

## 2. Dependency Tracking and Perturbation Radii

For a node $v$ incorporated at step $T(v)$ with parent $u$, the invariant is that $w(u,v)$ was the global minimum across the cut separating $S_{T(v)-1}$ from the rest.

On a weight update of edge $(x,y)$, with $x$ extracted no later than $y$:

1. **Weight decrease** — $y$'s queue entry becomes $(w_{new}, y, x)$. Comparing this tuple (heap order: key, then node id) against stored extraction slots finds the *first* slot it would preempt.
   - No preemption and $y$ already extracted → patch its slot or do nothing ($O(1)$–$O(\text{slot distance})$).
   - Preempts slot $k$ → roll back to step $k$ and replay only the suffix, re-seeding frontier keys from the surviving prefix in $O(V + E)$.
   - $y$ unreachable so far → appended as a new extraction (keeps forests correct on disconnected graphs).
2. **Weight increase / deletion** — only matters if $(x,y)$ is $y$'s tree edge; an equal-cost replacement patches in place, otherwise rebuild from $y$'s slot (orphaned subtrees fall out automatically).

Non-tree-edge increases never invalidate anything (cycle property), which is where most fast repairs come from.

## Contract

The structure maintains the MST of the **root's connected component**
(node `root`, default 0). Nodes disconnected from the root are absent
from `get_mst_edges()` — combine with DynamicKruskal/DynamicBoruvka when
a full spanning forest is needed.

## 3. Measured behavior

`benchmark.py` (vs an independent textbook heap-Prim restart): 76–86% of
updates avoid any suffix replay on sparse random graphs (n=200–500);
updates run ~17–23x faster than full recomputation. Under the adversarial
config (always raising the lightest tree edge) it still holds 89%
fast-repairs at ~38x.

**Complexity honesty:** a suffix replay re-derives frontier keys with a
boundary scan of the surviving prefix — worst case $O(V+E)$ per rebuild.
Sub-linear rebuilds need per-step snapshots ($O(V)$ memory each) or a
rollback-capable decrease-key queue; neither fits Python's `heapq`, so
this is a deliberate tradeoff. Validated by `tests/fuzz_oracle.py`
against an independent Kruskal oracle restricted to the root component,
including deletions that disconnect the graph.
