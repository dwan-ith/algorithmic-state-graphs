from math import inf

class DynamicBoruvka:
    def __init__(self, n):
        self.n = n
        self.adj = [{} for _ in range(n)]
        
        # self.levels[lvl]['comp_id'][v] -> component id of v AT THE START of level 'lvl'
        # self.levels[lvl]['certs'][C] -> (u, v, w) cheapest edge leaving C
        # self.levels[lvl]['edges'] -> list of edges selected at this level
        self.levels = []
        
        self.fast_repairs = 0
        self.rebuilds_triggered = 0

    def add_edge(self, u, v, w):
        self.adj[u][v] = w
        self.adj[v][u] = w

    def get_mst_edges(self):
        mst = []
        for lvl in self.levels:
            mst.extend(lvl['edges'])
        return sorted(mst)

    def _compute_from_level(self, start_lvl):
        # Truncate levels
        self.levels = self.levels[:start_lvl]
        
        if start_lvl == 0:
            comp_id = list(range(self.n))
        else:
            # We need to construct the comp_id AFTER the merges of start_lvl - 1
            # By definition, the comp_id AT THE START of the NEXT level is what we need.
            comp_id = self._merge_components(self.levels[-1]['comp_id'], self.levels[-1]['certs'])

        while len(set(comp_id)) > 1:
            lvl_state = {
                'comp_id': list(comp_id),
                'certs': {},
                'edges': []
            }
            
            # Find certificates
            for u in range(self.n):
                cu = comp_id[u]
                for v, w in self.adj[u].items():
                    cv = comp_id[v]
                    if cu != cv:
                        if cu not in lvl_state['certs'] or w < lvl_state['certs'][cu][2]:
                            lvl_state['certs'][cu] = (u, v, w)
                            
            if not lvl_state['certs']: # Disconnected
                break
                
            # Merge components and record edges
            parent = {c: c for c in set(comp_id)}
            def find(i):
                if parent[i] == i: return i
                parent[i] = find(parent[i])
                return parent[i]
                
            selected = []
            for cu, (u, v, w) in lvl_state['certs'].items():
                r1, r2 = find(comp_id[u]), find(comp_id[v])
                if r1 != r2:
                    parent[r1] = r2
                    selected.append((min(u,v), max(u,v), w))
                    
            lvl_state['edges'] = selected
            self.levels.append(lvl_state)
            
            # Advance comp_id for the next round
            for i in range(self.n):
                comp_id[i] = find(comp_id[i])

    def _merge_components(self, comp_id, certs):
        parent = {c: c for c in set(comp_id)}
        def find(i):
            if parent[i] == i: return i
            parent[i] = find(parent[i])
            return parent[i]
            
        for cu, (u, v, w) in certs.items():
            r1, r2 = find(comp_id[u]), find(comp_id[v])
            if r1 != r2:
                parent[r1] = r2
                
        new_comp = list(comp_id)
        for i in range(self.n):
            new_comp[i] = find(comp_id[i])
        return new_comp

    def compute_initial(self):
        self._compute_from_level(0)

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
        
        # Find the first level where this edge changes a certificate
        invalidated_level = None
        
        for lvl in range(len(self.levels)):
            state = self.levels[lvl]
            cu, cv = state['comp_id'][u], state['comp_id'][v]
            
            if cu == cv:
                # Same component, this edge is internal and cannot be a certificate
                continue
                
            if w_new < w_old:
                # Decreased weight. Does it beat the existing certificate?
                best_u = state['certs'].get(cu, (None, None, inf))[2]
                best_v = state['certs'].get(cv, (None, None, inf))[2]
                
                if w_new < best_u or w_new < best_v:
                    invalidated_level = lvl
                    break
            else:
                # Increased weight. Was it the certificate?
                cert_u = state['certs'].get(cu)
                cert_v = state['certs'].get(cv)
                
                # Check if the specific edge (u, v) or (v, u) was the certificate
                if (cert_u and (cert_u[0] == u and cert_u[1] == v or cert_u[0] == v and cert_u[1] == u)):
                    invalidated_level = lvl
                    break
                if (cert_v and (cert_v[0] == u and cert_v[1] == v or cert_v[0] == v and cert_v[1] == u)):
                    invalidated_level = lvl
                    break
                    
        if invalidated_level is not None:
            self.rebuilds_triggered += 1
            self._compute_from_level(invalidated_level)
        elif (w_new != inf
              and self._final_components()[u] != self._final_components()[v]):
            # No stored certificate changed, but the update joins two
            # components that the stored level chain keeps separate -- this
            # happens once the chain stopped early on a disconnected graph.
            # Extend the chain past its last level instead of ignoring it.
            self.rebuilds_triggered += 1
            self._compute_from_level(len(self.levels))
        else:
            self.fast_repairs += 1

    def _final_components(self):
        """Component partition implied by all stored levels."""
        if not self.levels:
            return list(range(self.n))
        comp = self.levels[0]['comp_id']
        for lvl in self.levels:
            comp = self._merge_components(comp, lvl['certs'])
        return comp
