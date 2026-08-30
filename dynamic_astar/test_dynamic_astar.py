import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dynamic_astar import DynamicAStar
from core.graph_generator import generate_random_connected_graph, get_locality_perturbation

def test_astar():
    n = 200
    edges = generate_random_connected_graph(n, 0.05)
    
    dyn_a = DynamicAStar(n, 0, n-1)
    for u, v, w in edges:
        dyn_a.add_edge(u, v, w)
        
    dyn_a.compute_initial()
    initial_dist = dyn_a.g[n-1]
    
    updates = 100
    for i in range(updates):
        u, v, w_new = get_locality_perturbation(edges, n)
        
        dyn_a.update_edge(u, v, w_new)
        dyn_dist = dyn_a.g[n-1]
        
        st = DynamicAStar(n, 0, n-1)
        for eu, ev, ew in edges:
            st.add_edge(eu, ev, ew)
        st.compute_initial()
        st_dist = st.g[n-1]
        
        if dyn_dist != st_dist:
            print(f"Error at update {i}: {u}-{v}={w_new} (Weight Dyn: {dyn_dist}, St: {st_dist})")
            assert False, "Weights mismatched!"
            
    print("A* (LPA*) tests passed!")
    print(f"--- METRICS ---")
    print(f"Updates: {updates}")
    print(f"Fast Repairs (Near-instant propagation): {dyn_a.fast_repairs}")
    print(f"Total Incremental Vertex Expansions: {dyn_a.node_expansions}")

if __name__ == "__main__":
    test_astar()
