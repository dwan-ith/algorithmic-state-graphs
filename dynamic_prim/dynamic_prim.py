import heapq
from math import inf


class DynamicPrim:
    """
    Persistent Prim execution trace with incremental repair.

    Contract: the structure maintains the MST of the ROOT'S CONNECTED
    COMPONENT (node ``root``, default 0).  Nodes outside that component --
    initially, or after deletions disconnect them -- are simply absent
    from ``get_mst_edges()``.  This mirrors the per-source scoping of the
    shortest-path modules; combine with DynamicKruskal/DynamicBoruvka when
    a full spanning forest is required.

    State
    -----
    trace[i], trace_key[i], trace_parent[i]
        The i-th node Prim extracted, its cut weight, and its MST parent.
    extraction_step[v]
        Step at which v was extracted (-1 if not yet / unreachable).

    Repair model
    ------------
    Weight decrease: find the first stored slot that v's candidate entry
    (w_new, v, u) would preempt (exact heap-tuple order -- key, then node
    id, then parent, matching the replay queue).  Roll back to that slot
    and replay only the suffix; otherwise patch the slot, append v as a
    new tail extraction, or do nothing.

    Weight increase or deletion: only tree edges matter (cycle property).
    An equal-or-better replacement connection patches v's slot in place;
    otherwise roll back to v's slot and replay the suffix (orphaned
    subtrees fall out automatically because their frontier keys become
    infinite).

    Complexity honesty: a suffix replay re-derives frontier keys by
    scanning the boundary of the surviving prefix, which is O(V + E) in
    the worst case per rebuild.  Sub-linear rebuilds would require either
    per-step frontier snapshots (O(V) memory each) or a decrease-key
    priority queue with historical rollback; both are deliberate non-goals
    here (heapq exposes neither decrease-key nor rollback).  Fast repairs,
    which are the common case on sparse graphs, avoid replay entirely.
    """

    def __init__(self, n, root=0):
        self.n = n
        self.root = root
        self.adj = [{} for _ in range(n)]

        self.trace = []          # trace[i]        = node extracted at step i
        self.trace_key = []      # trace_key[i]    = cut weight at extraction
        self.trace_parent = []   # trace_parent[i] = MST parent

        self.extraction_step = [-1] * n   # -1 => not (yet) in the tree

        self.fast_repairs = 0
        self.rebuilds_triggered = 0
        # Sensitivity tracking: how many steps were re-run per update
        self.affected_steps_total = 0

    def add_edge(self, u, v, w):
        self.adj[u][v] = w
        self.adj[v][u] = w

    def get_mst_edges(self):
        edges = []
        for i in range(1, len(self.trace)):
            u = self.trace[i]
            p = self.trace_parent[i]
            w = self.trace_key[i]
            if p != -1 and w != inf:
                edges.append((min(u, p), max(u, p), w))
        return sorted(edges)

    # ------------------------------------------------------------------
    # frontier mechanics
    # ------------------------------------------------------------------

    def _resume_from_step(self, step):
        """Roll back the trace to `step` and re-run Prim forward from there."""
        steps_rerun = len(self.trace) - step
        self.affected_steps_total += steps_rerun

        es = self.extraction_step
        for node in self.trace[step:]:
            es[node] = -1

        self.trace = self.trace[:step]
        self.trace_key = self.trace_key[:step]
        self.trace_parent = self.trace_parent[:step]

        # Re-derive frontier keys from the surviving prefix tree.
        current_keys = [inf] * self.n
        current_parents = [-1] * self.n

        if step == 0:
            current_keys[self.root] = 0
        else:
            in_tree = set(self.trace)
            for v in range(self.n):
                if v not in in_tree:
                    for nb, w in self.adj[v].items():
                        if nb in in_tree and w < current_keys[v]:
                            current_keys[v] = w
                            current_parents[v] = nb

        # Heapify only reachable candidates; unreachable nodes join via the
        # append path of _repair_decrease if they ever become connected.
        pq = [(current_keys[v], v, current_parents[v])
              for v in range(self.n)
              if es[v] == -1 and current_keys[v] != inf]
        heapq.heapify(pq)

        while pq:
            w, u, p = heapq.heappop(pq)
            if es[u] != -1 or w > current_keys[u]:
                continue                      # superseded entry
            s = len(self.trace)
            es[u] = s
            self.trace.append(u)
            self.trace_key.append(w)
            self.trace_parent.append(p)

            for nb, weight in self.adj[u].items():
                if es[nb] == -1 and weight < current_keys[nb]:
                    current_keys[nb] = weight
                    current_parents[nb] = u
                    heapq.heappush(pq, (weight, nb, u))

    def compute_initial(self):
        self._resume_from_step(0)

    # ------------------------------------------------------------------
    # updates
    # ------------------------------------------------------------------

    def update_edge(self, u, v, w_new):
        w_old = self.adj[u].get(v, inf)
        if w_old == w_new:
            return

        if w_new == inf:
            self.adj[u].pop(v, None)
            self.adj[v].pop(u, None)
        else:
            self.adj[u][v] = w_new
            self.adj[v][u] = w_new

        tu = self.extraction_step[u]
        tv = self.extraction_step[v]

        if tu == -1 and tv == -1:
            # Both endpoints lie outside the tracked tree: the change is
            # internal to (or between) orphan components of a disconnected
            # graph, so the trace cannot be affected.
            self.fast_repairs += 1
            return

        # Canonicalise: tu <= tv (u extracted no later than v; tv may be -1).
        if tv != -1 and (tu == -1 or tu > tv):
            tu, tv = tv, tu
            u, v = v, u

        if w_new < w_old:
            self._repair_decrease(u, v, w_new, tu, tv)
        else:
            self._repair_increase(u, v, w_new, tu, tv)

    def _repair_decrease(self, u, v, w_new, tu, tv):
        """Weight decrease / edge insertion."""
        limit = len(self.trace) if tv == -1 else tv + 1
        preempt_step = None
        for k in range(tu + 1, limit):
            if (w_new, v, u) < (self.trace_key[k], self.trace[k],
                                self.trace_parent[k]):
                preempt_step = k
                break

        if preempt_step is not None:
            # v joins the tree earlier: everything from that slot onward can
            # diverge, so roll back and replay the suffix.
            self.rebuilds_triggered += 1
            self._resume_from_step(preempt_step)
        elif tv == -1:
            # v just became connected to the root component.  Its own
            # relaxation can transitively reconnect further orphans, so a
            # purely local append is insufficient -- replay cleanly from
            # the root (rare event; full cost is honest here).
            self.rebuilds_triggered += 1
            self._resume_from_step(0)
        elif w_new < self.trace_key[tv]:
            # v keeps its position but connects through the cheaper edge.
            self.trace_key[tv] = w_new
            self.trace_parent[tv] = u
            self.fast_repairs += 1
        else:
            # No stored key is beaten: fresh Prim would extract the exact
            # same sequence again.
            self.fast_repairs += 1

    def _repair_increase(self, u, v, w_new, tu, tv):
        """Weight increase / edge deletion."""
        if tv == -1:
            # The later endpoint is outside the tree; nothing invalidated.
            self.fast_repairs += 1
            return

        if self.trace_parent[tv] != u:
            # Non-tree edge got heavier: MST unaffected by the cycle property.
            self.fast_repairs += 1
            return

        # Tree edge (u -> v) grew.  Any replacement parent must have been
        # extracted before v; scan once for the best prefix connection
        # (extraction-step bounds instead of building a prefix set).
        es = self.extraction_step
        best_alt = inf
        best_nb = -1
        for nb, wt in self.adj[v].items():
            s_nb = es[nb]
            if 0 <= s_nb < tv and wt < best_alt:
                best_alt = wt
                best_nb = nb

        if best_alt <= self.trace_key[tv]:
            # Replacement of equal-or-lower cost exists; v keeps its slot.
            self.trace_key[tv] = best_alt
            self.trace_parent[tv] = best_nb
            self.fast_repairs += 1
        else:
            # v's key increases: its slot and everything after may reorder.
            self.rebuilds_triggered += 1
            self._resume_from_step(tv)
