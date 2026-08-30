# Dynamic Kruskal: Chronological Rank Repair

## 1. Persistent State

Kruskal's decisions form a chronological sequence over a globally sorted edge
list. The persistent state is:

- `sorted_edges`: current sorted list of $(w, u, v)$ triples,
- `mst_set` / `in_mst`: the accepted set with $O(1)$ membership.

No per-edge DSU snapshots are stored; instead a DSU is re-seeded from any
prefix on demand.

## 2. Update Handling

A weight change relocates the edge from `idx_old` to `idx_new` in the sorted
list (deletion removes it entirely).

- **Fast path 1 — non-MST increase**: a heavier non-tree edge moves later;
  it was rejected before (endpoints already connected by strictly earlier
  edges) and stays rejected. $O(\log E)$ bookkeeping only.
- **Fast path 2 — MST decrease**: by the cycle property the same tree
  remains minimum; pure weight-bookkeeping.
- **Fast path 3 — non-MST decrease**: if endpoints are still connected
  under the accepted edges preceding its new position, it stays rejected.
- Otherwise rebuild from the earliest affected rank (`min(idx_old, idx_new)`)
  with a fresh prefix DSU and replay only the suffix. MST entries at or after
  that rank — including the relocated/deleted edge itself — are purged first,
  so stale memberships cannot survive deletions.
- Inserting a brand-new edge is handled by the same path (`idx_old = -1`).
- The prefix DSU unions only *accepted* prefix edges (connectivity-
  equivalent): $O(n\,\alpha)$ instead of one union per prefix edge.

## 3. Honest complexity note

Fast paths are $O(n\,\alpha)$ (one list scan + small DSU), not $O(\log)$.
Rebuilds replay a suffix of the sorted list, so globally ordered state
remains inherently sensitive: under adversarial targeted increases on tree
edges fast repairs drop to 0% (updates still ~2.3x faster than restart,
since the suffix shrinks as weights grow). For fully-dynamic adversarial
MST, link-cut/topology trees are the right structures.

## 4. Measured behavior

`benchmark.py` (vs an independent textbook Kruskal restart): 82–92% fast
repairs, ~4.4–9.1x faster than full recomputation on sparse random graphs.
Validated by `tests/fuzz_oracle.py` against an independent Kruskal oracle.
