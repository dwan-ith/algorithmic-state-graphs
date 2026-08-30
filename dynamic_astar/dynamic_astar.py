import heapq
from math import inf


class DynamicAStar:
    """
    LPA* (Lifelong Planning A*) — incremental heuristic search.

    Local consistency: g(v) == rhs(v).
    rhs(v) = min over predecessors u of (g(u) + w(u,v)).  Start: rhs(s)=0.

    On an edge weight change, only the endpoints whose *incoming* edges changed
    become potentially inconsistent.  We update only those vertices.

    The h() function here returns 0 (Dijkstra-equivalent) so the underlying
    graph need not be embedded in a metric space.  Replace with a real
    admissible heuristic for faster search.
    """

    def __init__(self, n, start, goal):
        self.n = n
        self.start = start
        self.goal = goal
        self.adj = [{} for _ in range(n)]

        self.g = [inf] * n
        self.rhs = [inf] * n
        self.rhs[start] = 0

        # Priority queue stores (key, node).  We use lazy deletion: a node
        # is "active" only if it's in self.in_queue with the same key.
        self.pq = []
        self.in_queue = {}   # node -> current key tuple in queue

        self.node_expansions = 0
        self.fast_repairs = 0

    def add_edge(self, u, v, w):
        self.adj[u][v] = w
        self.adj[v][u] = w

    def h(self, u):
        return 0   # admissible zero heuristic (Dijkstra mode)

    def _key(self, u):
        m = min(self.g[u], self.rhs[u])
        return (m + self.h(u), m)

    def _insert(self, u):
        k = self._key(u)
        self.in_queue[u] = k
        heapq.heappush(self.pq, (k, u))

    def _remove(self, u):
        # Lazy deletion: just remove from in_queue; stale entry stays in heap.
        self.in_queue.pop(u, None)

    def _update_vertex(self, u):
        if u != self.start:
            best = inf
            for nb, w in self.adj[u].items():
                if self.g[nb] + w < best:
                    best = self.g[nb] + w
            self.rhs[u] = best

        self._remove(u)
        if self.g[u] != self.rhs[u]:
            self._insert(u)

    def _compute_shortest_path(self):
        while self.pq:
            # Skip stale entries
            k, u = self.pq[0]
            if self.in_queue.get(u) != k:
                heapq.heappop(self.pq)
                continue

            k_goal = self._key(self.goal)
            if k >= k_goal and self.rhs[self.goal] == self.g[self.goal]:
                break

            heapq.heappop(self.pq)
            self._remove(u)

            self.node_expansions += 1
            if self.g[u] > self.rhs[u]:
                self.g[u] = self.rhs[u]
                for nb in self.adj[u]:
                    self._update_vertex(nb)
            else:
                self.g[u] = inf
                self._update_vertex(u)
                for nb in self.adj[u]:
                    self._update_vertex(nb)

    def compute_initial(self):
        self._update_vertex(self.start)
        self._compute_shortest_path()

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

        expansions_before = self.node_expansions

        # Bug fix: in an undirected graph, changing edge (u,v) makes v's incoming
        # edge from u change, and u's incoming edge from v change.
        # Only update the vertices that actually have an incoming edge affected.
        self._update_vertex(v)   # rhs(v) may change via the (u->v) direction
        self._update_vertex(u)   # rhs(u) may change via the (v->u) direction

        self._compute_shortest_path()

        expansions_used = self.node_expansions - expansions_before
        if expansions_used == 0:
            self.fast_repairs += 1
