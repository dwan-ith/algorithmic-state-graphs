import heapq
from math import inf


class DynamicDijkstra:
    """
    Persistent Dijkstra SPT with incremental subtree repair.

    State: dist[v], parent[v], children[v] form the shortest-path tree.

    Weight decrease: new shortcut may improve distances; propagate forward.
    Weight increase: if the edge was the SPT edge for its downstream endpoint,
                     invalidate that subtree and re-seed from the boundary.
    """

    def __init__(self, n, root=0):
        self.n = n
        self.root = root
        self.adj = [{} for _ in range(n)]

        self.dist = [inf] * n
        self.parent = [-1] * n
        self.children = [set() for _ in range(n)]  # SPT children

        self.fast_repairs = 0
        self.rebuilds_triggered = 0
        self.affected_nodes_total = 0

    def add_edge(self, u, v, w):
        self.adj[u][v] = w
        self.adj[v][u] = w

    def get_distances(self):
        return list(self.dist)

    def _set_parent(self, v, p):
        old_p = self.parent[v]
        if old_p != -1 and old_p != p:
            self.children[old_p].discard(v)
        self.parent[v] = p
        if p != -1:
            self.children[p].add(v)

    def compute_initial(self):
        self.dist = [inf] * self.n
        self.dist[self.root] = 0
        for s in self.children:
            s.clear()
        self.parent = [-1] * self.n

        pq = [(0, self.root)]
        settled = [False] * self.n

        while pq:
            d, u = heapq.heappop(pq)
            if settled[u]:
                continue
            settled[u] = True
            for v, w in self.adj[u].items():
                if self.dist[u] + w < self.dist[v]:
                    self.dist[v] = self.dist[u] + w
                    self._set_parent(v, u)
                    heapq.heappush(pq, (self.dist[v], v))

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

        if w_new < w_old:
            # ---- WEIGHT DECREASE ----
            # Try both directions as a shortcut.
            improved = False
            pq = []
            for a, b in ((u, v), (v, u)):
                if self.dist[a] + w_new < self.dist[b]:
                    self.dist[b] = self.dist[a] + w_new
                    self._set_parent(b, a)
                    heapq.heappush(pq, (self.dist[b], b))
                    improved = True

            if not improved:
                self.fast_repairs += 1
                return

            self.rebuilds_triggered += 1
            while pq:
                d, curr = heapq.heappop(pq)
                if d > self.dist[curr]:
                    continue
                for nb, weight in self.adj[curr].items():
                    nd = self.dist[curr] + weight
                    if nd < self.dist[nb]:
                        self.dist[nb] = nd
                        self._set_parent(nb, curr)
                        heapq.heappush(pq, (nd, nb))

        else:
            # ---- WEIGHT INCREASE / DELETION ----
            # Find which endpoint (if any) is the *downstream* node in the SPT
            # for this edge.  Bug fix: check SPT parent direction explicitly.
            affected_root = None
            if self.parent[v] == u and self.dist[u] + w_old == self.dist[v]:
                affected_root = v
            elif self.parent[u] == v and self.dist[v] + w_old == self.dist[u]:
                affected_root = u

            if affected_root is None:
                self.fast_repairs += 1
                return

            self.rebuilds_triggered += 1

            # Collect the full subtree rooted at affected_root
            affected = set()
            stack = [affected_root]
            while stack:
                curr = stack.pop()
                affected.add(curr)
                stack.extend(self.children[curr])

            self.affected_nodes_total += len(affected)

            # Invalidate subtree state
            for node in affected:
                self.dist[node] = inf
                old_p = self.parent[node]
                self.parent[node] = -1
                if old_p != -1 and old_p not in affected:
                    self.children[old_p].discard(node)
            for node in affected:
                self.children[node].clear()

            # Re-seed from the subtree boundary: affected nodes connected to settled nodes
            pq = []
            for node in affected:
                for nb, weight in self.adj[node].items():
                    if nb not in affected and self.dist[nb] != inf:
                        nd = self.dist[nb] + weight
                        if nd < self.dist[node]:
                            self.dist[node] = nd
                            self._set_parent(node, nb)
                if self.dist[node] != inf:
                    heapq.heappush(pq, (self.dist[node], node))

            # Propagate within affected subtree
            while pq:
                d, curr = heapq.heappop(pq)
                if d > self.dist[curr]:
                    continue
                for nb, weight in self.adj[curr].items():
                    if nb in affected:
                        nd = self.dist[curr] + weight
                        if nd < self.dist[nb]:
                            self.dist[nb] = nd
                            self._set_parent(nb, curr)
                            heapq.heappush(pq, (nd, nb))
