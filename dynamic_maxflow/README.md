# Dynamic Max Flow: Residual Repair

## 1. Persistent State

Flow on a network is a *certificate*: a feasible flow of value $F$ plus an
empty residual cut is a proof of maximality. The implementation keeps

- directed capacities $\text{cap}(u,v)$,
- signed directional flows $f(u,v)$,
- residuals computed as $r(x,y) = \text{cap}(x,y) - f(x,y) + f(y,x)$,

so antiparallel directed edges never conflate their flows.

## 2. Update Classes

- **Capacity increase** — old flow stays feasible; augment forward while
  augmenting paths remain.
- **Capacity decrease, still feasible** ($f(u,v) \le c_{new}$) — shrink the
  residual; constant work.
- **Capacity decrease breaking feasibility** — excess
  $\Delta = f(u,v) - c_{new}$ units must leave edge $(u,v)$.

## 3. Feasibility Restoration (three phases)

1. **Reroute**: push up to $\Delta$ from $u$ to $v$ through *other* residual
   arcs (edge $(u,v)$ itself is forbidden), releasing those units from the
   constrained edge. Conservation holds at every node by construction.
2. **Cancel**: any remaining excess is removed from the s–t flow itself:
   walk back along flowing arcs $s \rightsquigarrow u$, forward along flowing
   arcs $v \rightsquigarrow t$, decrementing real flows; total flow value
   drops accordingly. A decomposition argument guarantees these paths exist
   whenever phase 1 falls short.
3. **Re-augment** forward to restore maximality.

Every push traverses strictly positive residuals or strictly positive flows,
so capacity constraints and conservation hold after every operation.

## Measured behavior (`benchmark.py`, n=200–300 sparse networks, vs an
independent dict-based Edmonds-Karp restart)

96% of mixed updates (small capacity changes incl. deletions) are pure fast
repairs; end-to-end updates run ~11–110x faster than recomputation. Under
the adversarial config — every update cuts an edge's capacity below its
current flow, forcing feasibility repair — the repair machinery keeps
correctness at ~3.2x speedup: violation repair costs real residual-search
work, and the benchmark reports that honestly. Validated by
`tests/fuzz_oracle.py` against the same independent oracle family.
