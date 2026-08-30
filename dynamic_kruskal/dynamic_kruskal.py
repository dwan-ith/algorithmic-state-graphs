import bisect
from math import inf


class DynamicKruskal:
    """
    Persistent Kruskal with incremental repair.

    Key design change from naive version: we do NOT store per-edge DSU snapshots
    (which cost O(E·V) memory).  Instead we track:
      - sorted_edges: the current sorted edge list
      - mst_set: set of edges currently in the MST (as (u,v,w) tuples)
      - in_mst: dict (u,v) -> bool for O(1) lookup

    On an edge update we find the earliest affected position in sorted_edges and
    re-run Kruskal from that position with a fresh DSU seeded from all edges
    before that position.

    Fast-repair condition: if the changed edge was rejected at both its old and
    new position (same-component endpoints), no MST change occurs.
    """

    def __init__(self, n):
        self.n = n
        self.edges = {}           # (u,v) canonical -> w
        self.sorted_edges = []    # (w, u, v) sorted list
        self.mst_set = set()      # set of (u,v,w) in current MST
        self.in_mst = {}          # (u,v) -> w for O(1) lookup

        self.fast_repairs = 0
        self.rebuilds = 0
        self.affected_edges_total = 0

    def add_edge(self, u, v, w):
        u, v = min(u, v), max(u, v)
        self.edges[(u, v)] = w

    # ---- DSU helpers ----
    def _make_dsu(self):
        return list(range(self.n)), [1] * self.n

    def _find(self, parent, i):
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:   # path compression
            parent[i], i = root, parent[i]
        return root

    def _union(self, parent, rank, a, b):
        ra, rb = self._find(parent, a), self._find(parent, b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1
        return True

    # ---- DSU seeded from a prefix of sorted_edges ----
    def _build_dsu_prefix(self, end_idx):
        """DSU reflecting Kruskal connectivity after sorted_edges[:end_idx].

        Unioning only the ACCEPTED prefix edges is connectivity-equivalent
        to unioning all of them (a rejected edge joins already-connected
        endpoints), so the cost is O(n * alpha) unions instead of one per
        prefix edge.
        """
        parent, rank = self._make_dsu()
        for i in range(end_idx):
            _, u, v = self.sorted_edges[i]
            if (u, v) in self.in_mst:
                self._union(parent, rank, u, v)
        return parent, rank

    def _run_from(self, start_idx, purge=frozenset()):
        """Re-run Kruskal from start_idx, repairing mst_set and in_mst.

        Removal candidates are MST edges sitting at or after start_idx in the
        current sorted list, plus every pair in `purge` -- needed because the
        caller has already relocated/removed the updated edge from
        sorted_edges, so a deleted edge would otherwise keep its stale MST
        membership forever.
        """
        mst_indices = {(u, v): w for u, v, w in self.mst_set}
        edges_to_remove = []
        for i in range(start_idx, len(self.sorted_edges)):
            _, u, v = self.sorted_edges[i]
            if (u, v) in mst_indices:
                edges_to_remove.append((u, v, mst_indices[(u, v)]))
        for pu, pv in purge:
            if (pu, pv) in mst_indices:
                edges_to_remove.append((pu, pv, mst_indices[(pu, pv)]))

        affected = len(self.sorted_edges) - start_idx
        self.affected_edges_total += affected

        for edge in set(edges_to_remove):
            self.mst_set.discard(edge)
            self.in_mst.pop((edge[0], edge[1]), None)

        # Seed DSU from the prefix
        parent, rank = self._build_dsu_prefix(start_idx)

        # Run from start_idx
        for i in range(start_idx, len(self.sorted_edges)):
            w, u, v = self.sorted_edges[i]
            if self._union(parent, rank, u, v):
                self.mst_set.add((u, v, w))
                self.in_mst[(u, v)] = w

    def compute_initial(self):
        self.sorted_edges = []
        for (u, v), w in self.edges.items():
            if w != inf:
                self.sorted_edges.append((w, u, v))
        self.sorted_edges.sort()
        self.mst_set.clear()
        self.in_mst.clear()
        self._run_from(0)

    def get_mst_edges(self):
        return sorted(self.mst_set)

    def update_edge(self, u, v, w_new):
        u, v = min(u, v), max(u, v)
        w_old = self.edges.get((u, v), inf)
        if w_new == w_old:
            return

        self.edges[(u, v)] = w_new

        # Locate old position in sorted list
        old_idx = -1
        if w_old != inf:
            pos = bisect.bisect_left(self.sorted_edges, (w_old, u, v))
            if pos < len(self.sorted_edges) and self.sorted_edges[pos] == (w_old, u, v):
                old_idx = pos

        if old_idx != -1:
            self.sorted_edges.pop(old_idx)

        new_idx = -1
        if w_new != inf:
            item = (w_new, u, v)
            new_idx = bisect.bisect_left(self.sorted_edges, item)
            self.sorted_edges.insert(new_idx, item)

        # Fast-repair paths -- each preserves the MST by an exchange argument.
        in_mst_old = (u, v) in self.in_mst

        if not in_mst_old:
            if w_new == inf:
                # Deleted a non-MST edge: nothing to do.
                self.fast_repairs += 1
                return
            if w_new > w_old:
                # A heavier non-tree edge moves LATER; it was rejected at its
                # old position (endpoints already connected by strictly
                # earlier edges) and the prefix only grows, so it stays
                # rejected.  No other decision can change.
                self.fast_repairs += 1
                return
            # Cheaper non-tree edge: it may now be accepted at its new,
            # earlier position.
            parent, rank = self._build_dsu_prefix(new_idx)
            if self._find(parent, u) == self._find(parent, v):
                self.fast_repairs += 1
                return
        elif w_new < w_old:
            # An MST edge got cheaper: by the cycle property the same tree
            # remains minimum, so this is pure bookkeeping.
            self.mst_set.discard((u, v, w_old))
            self.mst_set.add((u, v, w_new))
            self.in_mst[(u, v)] = w_new
            self.fast_repairs += 1
            return

        # Either an MST edge grew/shrank positionally, or a cheaper non-tree
        # edge must be reconsidered: rebuild the affected suffix.
        self.rebuilds += 1
        earliest = new_idx if old_idx == -1 else (old_idx if new_idx == -1 else min(old_idx, new_idx))
        self._run_from(earliest, purge={(u, v)})
