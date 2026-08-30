import collections
from math import inf


class DynamicMaxFlow:
    """
    Persistent max-flow with incremental residual repair.

    State: directed capacities cap[(u,v)] and a signed flow dictionary
    flow[(u,v)].  The residual of an ordered pair is

        r(x, y) = cap(x, y) - flow(x, y) + flow(y, x)

    so antiparallel directed edges are handled without conflating their
    flows (the previous matrix version silently granted phantom reverse
    capacity here).

    Update repair:
      * capacity increase          -> old flow stays feasible; augment forward.
      * capacity decrease, still   -> shrink residual; nothing else to do.
        feasible (net flow <= cap)
      * capacity decrease breaking -> (1) reroute: push the excess around the
        feasibility                   edge through other residual arcs,
                                      (2) cancel: route the excess back into
                                          s along flowing arcs and forward
                                          from v into t, lowering the total
                                          flow value,
                                      (3) re-augment to restore maximality.

    Every phase pushes only along strictly positive residuals / flows, so
    conservation and capacity constraints hold after every operation.
    """

    def __init__(self, n, source, sink):
        self.n = n
        self.s = source
        self.t = sink
        self.cap = {}     # (u, v) -> capacity (directed)
        self.flow = {}    # (u, v) -> signed directional flow
        self._adj = collections.defaultdict(set)

        self.flow_value = 0
        self.fast_repairs = 0
        self.augmentations = 0

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    def add_edge(self, u, v, capacity):
        if u == v or capacity <= 0 or capacity == inf:
            return
        self.cap[(u, v)] = self.cap.get((u, v), 0) + capacity
        self._adj[u].add(v)
        self._adj[v].add(u)

    def compute_initial(self):
        self.flow_value += self._augment_s_t()

    def get_max_flow(self):
        return self.flow_value

    # ------------------------------------------------------------------
    # residual machinery
    # ------------------------------------------------------------------

    def _residual(self, x, y):
        return (self.cap.get((x, y), 0) - self.flow.get((x, y), 0)
                + self.flow.get((y, x), 0))

    def _push(self, x, y, amount):
        """Send `amount` units along arc x -> y in the residual graph."""
        if (x, y) in self.cap:
            self.flow[(x, y)] = self.flow.get((x, y), 0) + amount
        else:
            self.flow[(y, x)] = self.flow.get((y, x), 0) - amount

    def _neighbours(self, x):
        return self._adj[x]

    def _find_residual_path(self, src, dst, forbidden=frozenset()):
        """BFS on positive residuals; returns arc list [(x, y), ...] or None."""
        parent = {src: None}
        q = collections.deque([src])
        while q:
            x = q.popleft()
            for y in self._neighbours(x):
                if y in parent or (x, y) in forbidden:
                    continue
                if self._residual(x, y) > 0:
                    parent[y] = x
                    if y == dst:
                        path = []
                        cur = y
                        while parent[cur] is not None:
                            path.append((parent[cur], cur))
                            cur = parent[cur]
                        path.reverse()
                        return path
                    q.append(y)
        return None

    def _find_flow_path(self, src, dst):
        """BFS over arcs carrying strictly positive directional flow."""
        if src == dst:
            return []
        parent = {src: None}
        q = collections.deque([src])
        while q:
            x = q.popleft()
            for y in self._neighbours(x):
                if y in parent:
                    continue
                if self.flow.get((x, y), 0) > 0:
                    parent[y] = x
                    if y == dst:
                        path = []
                        cur = y
                        while parent[cur] is not None:
                            path.append((parent[cur], cur))
                            cur = parent[cur]
                        path.reverse()
                        return path
                    q.append(y)
        return None

    def _bottleneck(self, path):
        return min(self._residual(x, y) for x, y in path)

    def _augment_s_t(self):
        """Run Edmonds-Karp from scratch-state; returns added flow."""
        added = 0
        while True:
            path = self._find_residual_path(self.s, self.t)
            if path is None:
                return added
            b = self._bottleneck(path)
            for x, y in path:
                self._push(x, y, b)
            self.flow_value += b
            added += b
            self.augmentations += 1

    # ------------------------------------------------------------------
    # incremental update
    # ------------------------------------------------------------------

    def update_edge(self, u, v, c_new):
        if u == v or c_new < 0 or c_new == inf:
            return
        c_old = self.cap.get((u, v), 0)
        if c_new == c_old:
            return

        if c_new > c_old:
            # ---- CAPACITY INCREASE ----
            self.cap[(u, v)] = c_new
            self._adj[u].add(v)
            self._adj[v].add(u)
            if self._augment_s_t() == 0:
                self.fast_repairs += 1
            return

        # ---- CAPACITY DECREASE / EDGE DELETION ----
        self.cap[(u, v)] = c_new
        excess = max(0, self.flow.get((u, v), 0) - c_new)
        if excess == 0:
            # Old directional flow still fits under the new capacity.
            self.fast_repairs += 1
            return

        need = excess
        forbidden = {(u, v), (v, u)}

        # Phase 1 -- reroute the excess around the constrained edge.
        while need > 0:
            path = self._find_residual_path(u, v, frozenset(forbidden))
            if path is None:
                break
            b = min(self._bottleneck(path), need)
            for x, y in path:
                self._push(x, y, b)
            self._push(u, v, -b)          # release b units on (u, v) itself
            need -= b

        # Phase 2 -- cancel remaining excess out of the s-t flow:
        # pull b units back from u to s and push them onward from v to t.
        while need > 0:
            back = self._find_flow_path(self.s, u)
            forth = self._find_flow_path(v, self.t)
            if back is None or forth is None:
                raise RuntimeError(
                    "flow repair invariant violated: cannot cancel excess")
            b = need
            if back:
                b = min(b, min(self.flow[(x, y)] for x, y in back))
            if forth:
                b = min(b, min(self.flow[(x, y)] for x, y in forth))
            for x, y in back:
                self.flow[(x, y)] -= b
            for x, y in forth:
                self.flow[(x, y)] -= b
            self._push(u, v, -b)
            self.flow_value -= b
            need -= b

        if c_new == 0:
            del self.cap[(u, v)]

        # Phase 3 -- restore maximality with the repaired residual network.
        self._augment_s_t()


if __name__ == "__main__":
    # tiny smoke check against a known example
    m = DynamicMaxFlow(4, 0, 3)
    m.add_edge(0, 1, 3)
    m.add_edge(0, 2, 2)
    m.add_edge(1, 2, 1)
    m.add_edge(1, 3, 2)
    m.add_edge(2, 3, 3)
    m.compute_initial()
    assert m.get_max_flow() == 5, m.get_max_flow()
    m.update_edge(2, 3, 2)          # bottleneck cut shrinks
    assert m.get_max_flow() == 4, m.get_max_flow()
    m.update_edge(2, 3, 6)          # capacity returns
    assert m.get_max_flow() == 5, m.get_max_flow()
    print("smoke ok")
