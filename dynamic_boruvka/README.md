# Dynamic Borůvka: Hierarchical Component Evolution

## 1. Algorithmic State Mechanics

Borůvka processes structural rounds $L_0, L_1, \dots$ (at most $O(\log V)$),
where every disjoint component emits its cheapest outgoing edge
(certificate) and components merge along those edges. The persistent state
stores per round:

- `comp_id`: the component id of each vertex at round start,
- `certs`: cheapest outgoing edge per component,
- `edges`: edges selected during that round.

## 2. Update Handling

1. Scan rounds in order: a **decrease** invalidates the first round where the
   new weight beats a certificate; an **increase** invalidates the first
   round where the updated edge *was* a certificate.
2. Truncate to that round and re-merge forward; earlier rounds are untouched.
3. If no stored certificate changed but the update joins two components the
   chain keeps separate (possible when the chain stopped early because the
   graph was disconnected), extend the chain past its last level — this case
   is what keeps spanning-*forest* outputs correct.
4. Otherwise: fast repair.

## 3. Measured behavior — and an honest structural limit

`benchmark.py` (vs an independent textbook Kruskal restart): 77–86% fast
repairs on sparse random graphs, but only **1.3–1.7x** end-to-end speedup:
each round's certificate scan touches the whole adjacency structure, so
rebuilds are expensive.

Under the adversarial config (always raising the lightest current tree
edge) fast repairs drop to **0%** and updates become **slower than full
recomputation (0.54x)**. This is structural, not a bug: Borůvka's state is
a hierarchy of merge rounds in global weight order, so a targeted attack
on tree edges invalidates every level. For adversarial fully-dynamic MST
workloads use link-cut/topology-tree structures; this module wins on
localized random workloads only.

Validated by `tests/fuzz_oracle.py` against an independent Kruskal oracle,
including disconnected graphs and re-connecting insertions.
